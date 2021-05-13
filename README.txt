README
Author: Rameez Saiyid

Client-Server program with aiortc for image detection with openCV.

Server:
- Initializes client offer-answer handshake.
- Generates a 2D image of a ball bouncing across the screen with numpy and openCV.
- Transfers frames to client with aiortc MediaStreamTrack.
- Receives client xy coordinate guess for center of ball and displays error.

Client:
- Responds to server offer-answer handshake.
- Receives frames from video stream
- Calculates center of ball for each frame by openCV moments
  (a group of pixels with a common attribute) after grayscaling.
- Sends xy coordinate guess to server
- Displays each received frame

To run:
python3 server.py [---signaling-host (Default: 127.0.0.1)] [---signaling-port (Default: 1234)]
python3 client.py [---signaling-host (Default: 127.0.0.1)] [---signaling-port (Default: 1234)]
