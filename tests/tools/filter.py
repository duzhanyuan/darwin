import subprocess
import os
import os.path
import logging
from time import sleep
from conf import DEFAULT_FILTER_PATH, VALGRIND_MEMCHECK


class Filter():

    def __init__(self, path=None, config_file=None, filter_name="filter", socket_path=None, monitoring_socket_path=None, pid_file=None, output="NONE", next_filter_socket_path="no", nb_thread=1, cache_size=0, thresold=101, log_level="-z"):
        self.filter_name = filter_name
        self.socket = socket_path if socket_path else "/tmp/{}.sock".format(filter_name)
        self.config = config_file if config_file else "/tmp/{}.conf".format(filter_name)
        self.path = path if path else "{}darwin_{}".format(DEFAULT_FILTER_PATH, filter_name)
        self.monitor = monitoring_socket_path if monitoring_socket_path else "/tmp/{}_mon.sock".format(filter_name)
        self.pid = pid_file if pid_file else "/tmp/{}.pid".format(filter_name)
        self.cmd = [self.path, self.filter_name, self.socket, self.config, self.monitor, self.pid, output, next_filter_socket_path, str(nb_thread), str(cache_size), str(thresold), log_level]
        self.process = None
        self.error_code = 99 # For valgrind testing

    def __del__(self):
        if self.process and self.process.poll() is None:
            if VALGRIND_MEMCHECK is False:
                self.stop()
            else:
                self.valgrind_stop()
        self.clean_files()

    def check_start(self):
        if not os.path.exists(self.pid):
            logging.error("No PID file at start, maybe filter crashed")
            return False
        return True

    def check_stop(self):
        if os.path.exists(self.pid):
            logging.error("PID file not removed when stopping, maybe filter crashed")
            return False
        return True

    def start(self):
        self.process = subprocess.Popen(self.cmd)
        sleep(2)
        return self.check_start()

    def check_run(self):
        if self.process and self.process.poll() is None:
            return True

        return False

    def stop(self):
        self.process.terminate()
        try:
            self.process.wait(3)
        except subprocess.TimeoutExpired:
            logging.error("Unable to stop filter properly... Killing it.")
            self.process.kill()
            self.process.wait()
            return False
        return self.check_stop()

    def valgrind_start(self):
        if VALGRIND_MEMCHECK is False:
            return self.start()
        command = ['valgrind',
                   '--tool=memcheck',
                   '--leak-check=yes',
                   '-q', # Quiet mode so it doesn't pollute the output
                   '--error-exitcode={}'.format(self.error_code), #If valgrind report error on the run, return this exitcode.
                   ] + self.cmd

        self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        sleep(3)
        return self.check_start()

    def valgrind_stop(self):
        if VALGRIND_MEMCHECK is False:
            return self.stop()
        sleep(3)
        self.process.terminate()
        try:
            self.process.wait(15) # Valgrind can take some times, so it need a generous timeout
        except subprocess.TimeoutExpired:
            logging.error("Unable to stop filter properly... Killing it.")
            self.process.kill()
            self.process.wait()
            return False

        # If valgrind return the famous error code
        if self.process.returncode == self.error_code :
            out, err = self.process.communicate()
            logging.error("Valgrind returned error code: {}".format(self.process.returncode))
            logging.error("Valgrind error: {}".format(err))
            return False

        return self.check_stop()

    def clean_files(self):

        try:
            os.remove(self.config)
        except:
            pass

        try:
            os.remove(self.socket)
        except:
            pass

        try:
            os.remove(self.monitor)
        except:
            pass

        try:
            os.remove(self.pid)
        except:
            pass


    def configure(self, config):
        with open(self.config, 'w') as f:
            f.write(config)
