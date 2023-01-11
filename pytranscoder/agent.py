import socket
import os
import subprocess


class Agent:

    def run(self):
        s = socket.socket()
        port = 9567

        s.bind(("192.168.2.64", port))

        s.listen(1)
        print(f"listening on port {port}...")

        while True:
            c, addr = s.accept()
            print('got connection from addr', addr)
            hello = c.recv(2048).decode()
            print(hello)
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
                        chunk = c.recv(min(4096, filesize))
                        filesize -= len(chunk)
                        f.write(chunk)

                cli = cli.replace(r"{FILENAME}", output_filename)
                cli_parts = cli.split(r"$")
                print("receive complete - executing " + " ".join(cli_parts))
                cli_parts.append(tmp_filename)

                with subprocess.Popen(cli_parts,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT,
                                      universal_newlines=True,
                                      shell=False) as proc:
                    while proc.poll() is None:
                        line = proc.stdout.readline()
                        c.send(bytes(line.encode()))

                    c.send(bytes(0))
                    c.send(bytes(str(proc.returncode).encode()))
                    c.send(bytes(0))

            c.close()
