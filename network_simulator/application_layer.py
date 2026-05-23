from utils import log

class DNSService:
    def __init__(self):
        self.table = {'google.com': '142.250.0.1', 'example.com': '93.184.216.34', 'hostb.local': '192.168.2.2'}

    def query(self, domain):
        log('APP', f'DNS Query: What is the IP for {domain}?')
        ip = self.table.get(domain)
        log('APP', f'DNS Response: {domain} -> {ip}')
        return ip

class HTTPService:
    def request(self, path='/index.html'):
        req = f'GET {path} HTTP/1.1'
        log('APP', f'HTTP Request created: {req}')
        return req

    def response(self):
        res = 'HTTP/1.1 200 OK\\r\\nContent: Hello from HostB'
        log('APP', 'HTTP Response: 200 OK — "Hello from HostB"')
        return res

class FTPService:
    def run_demo(self):
        steps = [('CONNECT','220 FTP Service Ready'),('LIST','file1.txt file2.pdf'),('STOR report.txt','226 Upload complete'),('RETR file1.txt','226 Download complete'),('QUIT','221 Goodbye')]
        for cmd, res in steps:
            log('APP', f'FTP Client -> Server: {cmd}')
            log('APP', f'FTP Server -> Client: {res}')

class SSHService:
    def run_demo(self):
        log('APP', 'SSH: remote login established on port 22')
        log('APP', 'SSH Client command: ls')
        log('APP', 'SSH Server response: main.py README.md network_simulator/')
