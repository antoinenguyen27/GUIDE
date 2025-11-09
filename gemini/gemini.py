# -*- coding: utf-8 -*-
# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
## Setup

To install the dependencies for this script, run:

``` 
pip install google-genai opencv-python pyaudio pillow mss
```

Before running this script, ensure the `GOOGLE_API_KEY` environment
variable is set to the api-key you obtained from Google AI Studio.

Important: **Use headphones**. This script uses the system default audio
input and output, which often won't include echo cancellation. So to prevent
the model from interrupting itself it is important that you use headphones. 

## Run

To run the script:

```
python Get_started_LiveAPI.py
```

The script takes a video-mode flag `--mode`, this can be "camera", "screen", or "none".
The default is "camera". To share your screen run:

```
python Get_started_LiveAPI.py --mode screen
```
"""

import asyncio
import io
import json
import os
import subprocess
import sys
import traceback
from copy import deepcopy
from typing import Any, Dict, List, Optional

import cv2
import pyaudio
import PIL.Image
import mss


import argparse
import logging

from google import genai
from google.genai import types

try:
    from .home_layout import DEFAULT_HOME_LAYOUT
    from .preference_service import PreferenceService
except ImportError:
    from home_layout import DEFAULT_HOME_LAYOUT
    from preference_service import PreferenceService

if sys.version_info < (3, 11, 0):
    import taskgroup, exceptiongroup

    asyncio.TaskGroup = taskgroup.TaskGroup
    asyncio.ExceptionGroup = exceptiongroup.ExceptionGroup

FORMAT = pyaudio.paInt16
CHANNELS = 1
SEND_SAMPLE_RATE = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE = 1024
AUDIO_MIME_TYPE = f"audio/pcm;rate={SEND_SAMPLE_RATE}"

MODEL = "models/gemini-2.5-flash-native-audio-preview-09-2025"
DEFAULT_CAMERA_INDEX = 0

DEFAULT_MODE = "camera"

client = genai.Client(http_options={"api_version": "v1alpha"})

# Runtime preference/state helpers -------------------------------------------------
PREFERENCE_SERVICE = PreferenceService(
    initial_object_locations=deepcopy(DEFAULT_HOME_LAYOUT)
)


def resolve_camera_index(camera_name: Optional[str], explicit_index: Optional[int]) -> Optional[int]:
    """Resolve the desired camera index for OpenCV."""
    if explicit_index is not None:
        return explicit_index
    if not camera_name or sys.platform != "darwin":
        return None
    try:
        output = subprocess.check_output(
            ["system_profiler", "-json", "SPCameraDataType"], text=True
        )
        report = json.loads(output)
    except (subprocess.SubprocessError, json.JSONDecodeError, OSError) as exc:
        print(
            f"Warning: unable to query camera list for '{camera_name}': {exc}",
            file=sys.stderr,
        )
        return None

    cameras = report.get("SPCameraDataType", [])
    sorted_cameras = sorted(
        cameras, key=lambda cam: cam.get("spcamera_unique-id", "")
    )
    for idx, cam in enumerate(sorted_cameras):
        name = cam.get("_name", "")
        if name and camera_name.lower() in name.lower():
            return idx

    print(
        f"Warning: camera named '{camera_name}' not found. Falling back to default.",
        file=sys.stderr,
    )
    return None


def build_tools() -> List[types.Tool]:
    """Return the current tool definitions for the Live API config."""
    return [
        types.Tool(
            function_declarations=PREFERENCE_SERVICE.function_declarations,
        )
    ]

system_prompt ="""
You are a helpful home robot and answer in a friendly tone. You are currently being introduced to the house and are following the user around. 
You must listen and watch as your user gives you a tour of the house and remember important details about the rooms, objects, and their locations.
Specifically, you should pay attention to: 
- Room names and their functions (e.g., Kitchen, Living Room)
- Object names and their locations (e.g., 'the vase is on the kitchen table')
- Any specific instructions or preferences given by the user

You must store this information in your internal memory as you go along so you can refer to it later when asked.
Objects should be stored heirarchically by their location in a dict, we have tools to help you with this.
Process preferences should be stored in a graph which we also have tools to help you with.

Once the user completes a set of instructions or section of the tour, such as "that's how we fold and organise our cloths", you should repeat back a summary of what you have learned so far to confirm your understanding.
Then, you should ask any clarifying questions based on what you have learned so far and the memory stores you have built up. 
"""


CONFIG = types.LiveConnectConfig(
    response_modalities=["AUDIO"],
    system_instruction=system_prompt,
    proactivity=types.ProactivityConfig(proactive_audio=True),
    tools=build_tools(),
)

pya = pyaudio.PyAudio()


class AudioLoop:
    def __init__(self, video_mode=DEFAULT_MODE, camera_index: Optional[int] = None):
        self.video_mode = video_mode
        self.camera_index = camera_index

        self.audio_in_queue = None
        self.out_queue = None

        self.session = None

        self.send_text_task = None
        self.receive_audio_task = None
        self.play_audio_task = None
        self.preference_service = PREFERENCE_SERVICE
        self._tool_lock = asyncio.Lock()

    async def send_text(self):
        while True:
            text = await asyncio.to_thread(
                input,
                "message > ",
            )
            if text.lower() == "q":
                break
            content = types.Content(
                role="user", parts=[types.Part(text=text or ".")]
            )
            await self.session.send_client_content(turns=content, turn_complete=True)

    def _get_frame(self, cap):
        # Read the frameq
        ret, frame = cap.read()
        # Check if the frame was read successfully
        if not ret:
            return None
        # Fix: Convert BGR to RGB color space
        # OpenCV captures in BGR but PIL expects RGB format
        # This prevents the blue tint in the video feed
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = PIL.Image.fromarray(frame_rgb)  # Now using RGB frame
        img.thumbnail([1024, 1024])

        image_io = io.BytesIO()
        img.save(image_io, format="jpeg")
        image_io.seek(0)

        mime_type = "image/jpeg"
        image_bytes = image_io.read()
        return mime_type, image_bytes

    async def get_frames(self):
        # This takes about a second, and will block the whole program
        # causing the audio pipeline to overflow if you don't to_thread it.
        backend = cv2.CAP_AVFOUNDATION if sys.platform == "darwin" else cv2.CAP_ANY
        camera_id = self.camera_index if self.camera_index is not None else DEFAULT_CAMERA_INDEX
        cap = await asyncio.to_thread(cv2.VideoCapture, camera_id, backend)
        if not cap.isOpened():
            raise RuntimeError(
                f"Unable to open camera at index {camera_id}. Ensure the device is available and permitted."
            )

        while True:
            frame = await asyncio.to_thread(self._get_frame, cap)
            if frame is None:
                break

            await asyncio.sleep(1.0)

            mime_type, image_bytes = frame
            await self.out_queue.put(
                {"kind": "media", "mime_type": mime_type, "data": image_bytes}
            )

        # Release the VideoCapture object
        cap.release()

    def _get_screen(self):
        sct = mss.mss()
        monitor = sct.monitors[0]

        i = sct.grab(monitor)

        mime_type = "image/jpeg"
        image_bytes = mss.tools.to_png(i.rgb, i.size)
        img = PIL.Image.open(io.BytesIO(image_bytes))

        image_io = io.BytesIO()
        img.save(image_io, format="jpeg")
        image_io.seek(0)

        image_bytes = image_io.read()
        return mime_type, image_bytes

    async def get_screen(self):

        while True:
            frame = await asyncio.to_thread(self._get_screen)
            if frame is None:
                break

            await asyncio.sleep(1.0)

            mime_type, image_bytes = frame
            await self.out_queue.put(
                {"kind": "media", "mime_type": mime_type, "data": image_bytes}
            )

    async def send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            kind = msg.get("kind")
            if kind == "audio":
                blob = types.Blob(
                    data=msg["data"], mime_type=msg.get("mime_type", AUDIO_MIME_TYPE)
                )
                await self.session.send_realtime_input(media=blob)
            elif kind == "media":
                blob = types.Blob(data=msg["data"], mime_type=msg["mime_type"])
                await self.session.send_realtime_input(media=blob)

    async def listen_audio(self):
        mic_info = pya.get_default_input_device_info()
        self.audio_stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=SEND_SAMPLE_RATE,
            input=True,
            input_device_index=mic_info["index"],
            frames_per_buffer=CHUNK_SIZE,
        )
        if __debug__:
            kwargs = {"exception_on_overflow": False}
        else:
            kwargs = {}
        while True:
            data = await asyncio.to_thread(self.audio_stream.read, CHUNK_SIZE, **kwargs)
            await self.out_queue.put(
                {"kind": "audio", "data": data, "mime_type": AUDIO_MIME_TYPE}
            )

    async def receive_audio(self):
        "Background task to reads from the websocket and write pcm chunks to the output queue"
        while True:
            turn = self.session.receive()
            async for response in turn:
                if tool_call := getattr(response, "tool_call", None):
                    await self._handle_tool_call(tool_call)
                    continue
                if data := response.data:
                    self.audio_in_queue.put_nowait(data)
                    continue
                if text := response.text:
                    print(text, end="")

            # If you interrupt the model, it sends a turn_complete.
            # For interruptions to work, we need to stop playback.
            # So empty out the audio queue because it may have loaded
            # much more audio than has played yet.
            while not self.audio_in_queue.empty():
                self.audio_in_queue.get_nowait()

    async def play_audio(self):
        stream = await asyncio.to_thread(
            pya.open,
            format=FORMAT,
            channels=CHANNELS,
            rate=RECEIVE_SAMPLE_RATE,
            output=True,
        )
        while True:
            bytestream = await self.audio_in_queue.get()
            await asyncio.to_thread(stream.write, bytestream)

    async def _handle_tool_call(self, tool_call: types.LiveServerToolCall) -> None:
        function_calls = tool_call.function_calls or []
        if not function_calls:
            return
        async with self._tool_lock:
            responses = []
            for call in function_calls:
                name = getattr(call, "name", None)
                call_id = getattr(call, "id", None)
                if not name or call_id is None:
                    continue
                args = call.args or {}
                LOGGER.info("ToolCall start name=%s id=%s args=%s", name, call_id, args)
                tool_result = await asyncio.to_thread(
                    self._execute_tool_call, name, args
                )
                LOGGER.info(
                    "ToolCall end name=%s id=%s status=%s",
                    name,
                    call_id,
                    tool_result.get("status"),
                )
                responses.append(
                    types.FunctionResponse(
                        name=name,
                        response=tool_result,
                        id=call_id,
                    )
                )
            if responses:
                await self.session.send_tool_response(function_responses=responses)

    def _execute_tool_call(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        try:
            tool = self.preference_service.get_tool_callable(name)
        except KeyError:
            result = {
                "status": "error",
                "message": f"Tool {name!r} is not registered.",
            }
            LOGGER.error("ToolCall error name=%s detail=%s", name, result["message"])
            return result

        if not isinstance(args, dict):
            result = {
                "status": "error",
                "message": f"Tool arguments for {name!r} must be an object.",
            }
            LOGGER.error("ToolCall error name=%s detail=%s", name, result["message"])
            return result

        try:
            return tool(**args)
        except TypeError as exc:
            result = {
                "status": "error",
                "message": f"Invalid arguments for {name!r}: {exc}",
            }
            LOGGER.error("ToolCall error name=%s detail=%s", name, result["message"])
            return result
        except Exception as exc:
            result = {
                "status": "error",
                "message": f"Tool {name!r} failed: {exc}",
            }
            LOGGER.exception("ToolCall exception name=%s", name)
            return result

    async def run(self):
        try:
            async with (
                client.aio.live.connect(model=MODEL, config=CONFIG) as session,
                asyncio.TaskGroup() as tg,
            ):
                self.session = session

                self.audio_in_queue = asyncio.Queue()
                self.out_queue = asyncio.Queue(maxsize=5)

                send_text_task = tg.create_task(self.send_text())
                tg.create_task(self.send_realtime())
                tg.create_task(self.listen_audio())
                if self.video_mode == "camera":
                    tg.create_task(self.get_frames())
                elif self.video_mode == "screen":
                    tg.create_task(self.get_screen())

                tg.create_task(self.receive_audio())
                tg.create_task(self.play_audio())

                await send_text_task
                raise asyncio.CancelledError("User requested exit")

        except asyncio.CancelledError:
            pass
        except ExceptionGroup as EG:
            self.audio_stream.close()
            traceback.print_exception(EG)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        type=str,
        default=DEFAULT_MODE,
        help="pixels to stream from",
        choices=["camera", "screen", "none"],
    )
    parser.add_argument(
        "--camera-name",
        type=str,
        help="Preferred camera label (macOS only, e.g. 'FaceTime HD Camera').",
    )
    parser.add_argument(
        "--camera-index",
        type=int,
        help="Explicit cv2 camera index to use (overrides --camera-name).",
    )
    args = parser.parse_args()
    resolved_index = resolve_camera_index(args.camera_name, args.camera_index)
    main = AudioLoop(video_mode=args.mode, camera_index=resolved_index)
    asyncio.run(main.run())
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
LOGGER = logging.getLogger("gemini.tooling")
