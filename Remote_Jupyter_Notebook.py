import sys
import subprocess
import socket
import argparse
import paramiko
import pyperclip

# function to get available port
def get_free_port():
    """ return a available port ID on localhost """
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('localhost',0))
    s.listen(1)
    port = s.getsockname()[1]
    s.close()
    return port

# print out the output from paramiko SSH connection
def print_output(output):
    """ print stdout and stderr from SSH client """
    for line in output:
        print(line)

parser = argparse.ArgumentParser(description='Locally open IPython Notebook on remote server\n')
parser.add_argument('-t', '--terminate', dest='terminate', action='store_true', \
                    help='terminate the IPython notebook on remote server')
args = parser.parse_args()

host="your-host-name" # host name
user="your-username" # username

# write a temporary python script to upload to server to execute
# this python script will get available port number

def temp():
    with open('free_port_tmp.py', 'w') as f:
        f.write('import socket\nimport sys\n')
        f.write('def get_free_port():\n')
        f.write('    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n')
        f.write("    s.bind(('localhost', 0))\n")
        f.write('    s.listen(1)\n')
        f.write('    port = s.getsockname()[1]\n')
        f.write('    s.close()\n')
        f.write('    return port\n')
        f.write("sys.stdout.write('{}'.format(get_free_port()))\n")
        f.write('sys.stdout.flush()\n')

def connect():
    """
    connect to SSH server and launch jupyter notebook. create ssh tunneling
    between local machine and remote machine.
    """
    # create SSH client
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.load_system_host_keys()
    client.connect(host, username=user)

    # generate the temp file and upload to server
    temp()
    ftpClient = client.open_sftp()
    ftpClient.put('free_port_tmp.py', "/tmp/free_port_tmp.py")

    # execute python script on remote server to get available port id
    stdin, stdout, stderr = client.exec_command("python /tmp/free_port_tmp.py")
    stderr_lines = stderr.readlines()
    print_output(stderr_lines)

    port_remote = int(stdout.readlines()[0])
    print('REMOTE IPYTHON NOTEBOOK FORWARDING PORT: {}\n'.format(port_remote))

    ipython_remote_command = "source ~/.zshrc;tmux \
                              new-session -d -s remote_ipython_session 'ipython notebook \
                              --no-browser --port={}'".format(port_remote)

    stdin, stdout, stderr = client.exec_command(ipython_remote_command)
    stderr_lines = stderr.readlines()

    if len(stderr_lines) != 0:
        if 'duplicate session: remote_ipython_session' in stderr_lines[0]:
            print("ERROR: \"duplicate session: remote_ipython_session already exists\"\n")
            sys.exit(0)

    print_output(stderr_lines)

    # delete the temp files on local machine and server
    subprocess.run('rm -rf free_port_tmp.py', shell=True)
    client.exec_command('rm -rf /tmp/free_port_tmp.py')

    client.close()

    port_local = int(get_free_port())
    print('LOCAL SSH TUNNELING PORT: {}\n'.format(port_local))

    ipython_local_command = "ssh -N -f -L localhost:{}:localhost:{} \
                            gs27722@wel-145-31.cm.utexas.edu".format(port_local, port_remote)

    subprocess.run(ipython_local_command, shell=True)
    pyperclip.copy('http://localhost:{}'.format(port_local))


def close():
    # create SSH client
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.load_system_host_keys()
    client.connect(host, username=user)
    stdin, stdout, stderr = client.exec_command("source ~/.zshrc;tmux kill-session -t remote_ipython_session")
    stderr_lines = stderr.readlines()
    if len(stderr_lines) == 0:
        print('Successfully terminate the IPython notebook on {}\n'.format(host))
    else:
        print_output(stderr_lines)
    client.close()

    # kill the ssh tunneling on the local machine
    try:
        pid = int(subprocess.check_output("ps aux | grep localhost | grep -v grep | awk '{print $2}'", shell=True))
        subprocess.run("kill {}".format(pid), shell=True)
    except ValueError:
        pass

if args.terminate:
    close()
else:
    connect()
