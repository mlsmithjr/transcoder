import socket
import os
import subprocess
import time


class Agent:

    def run(self):
        s = socket.socket()
        port = 9567

        s.bind(("", port))

        s.listen(1)

        while True:
            print(f"listening on port {port}...")
            c, addr = s.accept()
            try:
                print('got connection from addr', addr)
                hello = c.recv(2048).decode()
                print(hello)
                if hello.startswith("PING"):
                    c.send(bytes("PONG".encode()))
                    c.close()
                    continue

                if hello.startswith("HELLO|"):

                    parts = hello.split("|")
                    if len(parts) < 5:
                        print("No enough values in HELLO packet: " + hello)
                        c.close()
                        continue

                    filesize = int(parts[1])
                    tempdir = parts[2]
                    filename = parts[3]
                    cli = parts[4]

                    print(" echoing back hello")
                    c.send(bytes(hello.encode()))

                    print(f"receiving {filesize} bytes to {filename}...")
                    output_filename = os.path.join(tempdir, filename)
                    tmp_filename = os.path.join(tempdir, filename + ".tmp")

                    with open(output_filename, "wb") as f:
                        while filesize > 0:
                            chunk = c.recv(min(1_000_000, filesize))
                            filesize -= len(chunk)
                            f.write(chunk)

                    cli = cli.replace(r"{FILENAME}", output_filename)
                    cli_parts = cli.split(r"$")
                    print("receive complete - executing " + " ".join(cli_parts))
                    cli_parts.append(tmp_filename)

                    vetoed = False
                    with subprocess.Popen(cli_parts,
                                          stdout=subprocess.PIPE,
                                          stderr=subprocess.STDOUT,
                                          universal_newlines=True,
                                          shell=False) as proc:
                        while proc.poll() is None:
                            line = proc.stdout.readline()
                            if line.startswith("video:"):
                                # transcode complete
                                break

                            c.send(bytes(line.encode()))

                            response = c.recv(4)
                            confirmation = response.decode()
                            print(confirmation)
                            if confirmation == "PING":
                                # ping received out of context, ignore
                                continue
                            if confirmation == "STOP":
                                proc.kill()
                                print("Client stopped the transcode, cleaning up")
                                vetoed = True
                                break
                            if confirmation == "VETO":
                                proc.kill()
                                print("Client vetoed the transcode, cleaning up")
                                vetoed = True
                                break
                            elif confirmation != "ACK!":
                                proc.kill()
                                print(f"Protocol error - expected ACK from client, got {confirmation}")
                                print("Cleaning up")
                                vetoed = True
                                break

                        while proc.poll() is None:
                            time.sleep(1)

                        if not vetoed:
                            if proc.returncode != 0:
                                print("> ERR")
                                c.send(bytes(f"ERR|{proc.returncode}".encode()))
                                print("Cleaning up")
                            else:
                                print("> DONE")
                                filesize = os.path.getsize(tmp_filename)
                                c.send(bytes(f"DONE|{proc.returncode}|{filesize}".encode()))
                                # wait for response, then send file
                                response = c.recv(4).decode()
                                if response == "ACK!":
                                    # send the file back
                                    print("sending transcoded file")
                                    with open(tmp_filename, "rb") as input_file:
                                        blk = input_file.read(1_000_000)
                                        while len(blk) > 0:
                                            c.send(blk)
                                            blk = input_file.read(1_000_000)
                                    print("done")
                        os.remove(tmp_filename)
                        os.remove(output_filename)

            except Exception as ex:
                print(str(ex))

            c.close()
