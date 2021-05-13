# CLIENT
import cv2
import numpy as np
import argparse
import asyncio
from multiprocessing import Process, Queue, Value
from aiohttp import web
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
from aiortc.contrib.signaling import BYE, TcpSocketSignaling, add_signaling_arguments, create_signaling

class FrameTransport(MediaStreamTrack):
    '''
    Wrapper class for MediaStreamTrack to receive frames from server.

    '''
    kind = "video"
    def __init__(self, track):
        super().__init__()
        self.track = track

    async def recv(self):
        '''
        Pass track's new frame from server.
                Return:
                        frame (VideoFrame): image frame

        '''
        frame = await self.track.recv()
        return frame

async def consume_signaling(pc, signaling):
    '''
    Maintains signal receive port and ICE candidate handshake
    Source:
    https://github.com/aiortc/aiortc/blob/f85f7133435b54ce9de5f2f391c0c0ef0014e820/examples/datachannel-cli/cli.py

            Parameters:
                    pc (RTCPeerConnection): Remote peer object
                    signaling (TcpSocketSignaling): Remote signal object

    '''
    while True:
        obj = await signaling.receive()

        if isinstance(obj, RTCSessionDescription):
            await pc.setRemoteDescription(obj)

            if obj.type == "offer":
                await pc.setLocalDescription(await pc.createAnswer())
                await signaling.send(pc.localDescription)
        elif isinstance(obj, RTCIceCandidate):
            await pc.addIceCandidate(obj)
        elif obj is BYE:
            print("Exiting")
            break

def imageParse(q, X, Y):
    '''
    Function for process_a, process center of detected moment into
    multiprocessing shared variables.

            Parameters:
                    q (Queue): multiprocessing queue for passing image data
                    X (Value): Shared variable for x coordinate
                    Y (Value): Shared variable for x coordinate

    '''
    img = q.get()
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    ret, thresh = cv2.threshold(gray, 0, 255, 0)
    M = cv2.moments(thresh)
    if (M["m00"] != 0):
        X.value = int(M["m10"] / M["m00"])
        Y.value = int(M["m01"] / M["m00"])

async def analyzeTrack(pc, track):
    '''
    Poll server for frame, predict ball center via Process, send coordinates
    over DataChannel.

            Parameters:
                    pc (RTCPeerConnection): Remote peer object
                    track (RemoteStreamTrack): object to receive server frames

    '''
    localVideo = FrameTransport(track)
    dc = pc.createDataChannel('coords')

    X = Value('i', 0)
    Y = Value('i', 0)
    process_q = Queue()

    while(True):
        try:
            process_a = Process(target = imageParse, args = (process_q, X, Y))
            process_a.start()
            frame = await localVideo.recv()

            img = frame.to_ndarray(format="bgr24")
            cv2.imshow("Client Feed", img)
            cv2.waitKey(1)
            process_q.put(img)
            process_a.join()
            dc.send("coords:" + str(X.value) + "," + str(Y.value))
        except Exception as e:
            print(e)



async def main(pc, signaling):
    '''
    Initializes RTC Event Listeners and server offer-answer handshake.

            Parameters:
                    pc (RTCPeerConnection): Remote peer object
                    signaling (TcpSocketSignaling): Remote signal object

    '''
    params = await signaling.connect()

    @pc.on("track")
    async def on_track(track):
        print("Track %s received" % track.kind)
        await analyzeTrack(pc, track)

    @pc.on("datachannel")
    def on_datachannel(channel):
        print(channel, "-", "created by remote party")

        @channel.on("message")
        def on_message(message):
            print(channel, "<", message)

    await consume_signaling(pc, signaling)


if __name__ == "__main__":
    print("Client started")
    parser = argparse.ArgumentParser(description="Ball Position Detector - Client")

    add_signaling_arguments(parser)
    args = parser.parse_args()

    signaling = TcpSocketSignaling(args.signaling_host, args.signaling_port)
    pc = RTCPeerConnection()

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            main(pc, signaling)
        )
    except KeyboardInterrupt:
        pass
    finally:
        # cleanup
        loop.run_until_complete(signaling.close())
        loop.run_until_complete(pc.close())
        loop.run_until_complete(cv2.destroyAllWindows())
