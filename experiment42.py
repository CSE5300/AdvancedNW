#CSE 5300, Spring 2019

from mininet.topo import Topo
from mininet.node import CPULimitedHost
from mininet.link import TCLink
from mininet.net import Mininet
from mininet.clean import cleanup
from mininet.log import lg, info
from mininet.util import dumpNodeConnections
from mininet.cli import CLI
import numpy as np
import matplotlib as mpl
mpl.use('Agg') 
import matplotlib.pyplot as plt
from subprocess import Popen, PIPE
from time import sleep, time
from multiprocessing import Process
from argparse import ArgumentParser
import sys
import os
import math

class TOPOLOGY(Topo):
    def build(self, bandwidth=1.2, delay=100):
        h1 = self.addHost('h1')
        h2 = self.addHost('h2')
        switch = self.addSwitch('s0')
        print "Bandwidth =", bandwidth * 1000.0, "Kbps"
        print "RTT =", 4 * delay, "ms"
        self.addLink(h1, switch, bw=bandwidth, delay="{}ms".format(delay))
        self.addLink(h2, switch, bw=bandwidth, delay="{}ms".format(delay))

def Run_Server(net):
    h1 = net.get('h1')
    proc = h1.popen("python http/webserver.py", shell=True)
    sleep(1)
    return [proc]


def setup(bandwidth=1.2, rtt=70):
    cleanup()
    os.system("sysctl -w net.ipv4.tcp_congestion_control=cubic > /dev/null")
    os.system("sysctl -w net.ipv4.tcp_retries1=100 > /dev/null")
    os.system("sysctl -w net.ipv4.tcp_retries2=100 > /dev/null")
    os.system("sysctl -w net.ipv4.tcp_frto=100 > /dev/null")
    os.system("sysctl -w net.ipv4.tcp_frto_response=100 > /dev/null")
    topo = TOPOLOGY(bandwidth=bandwidth, delay=rtt / 4.0)
    net = Mininet(topo=topo, host=CPULimitedHost, link=TCLink)
    net.start()
    return net


def clean(net):
    if net is not None:
        net.stop()
    Popen("pgrep -f webserver.py | xargs kill -9", shell=True).wait()
    Popen("killall -9 iperf", shell=True).wait()
    Popen("killall -9 ping", shell=True).wait()

def modify_route(host, initcwnd, initrwnd, mtu):
    rto_min = 1000
    route = host.cmd("ip route show").strip()
    print "route 1", route
    cmd = "sudo ip route change {} initcwnd {} initrwnd {} mtu {} rto_min {}".format(route, initcwnd, initrwnd, mtu, rto_min)
    print "cmd", cmd
    print "initcwnd", host.cmd(cmd)


def experiment(bandwidth, rtt, initcwnd, initrwnd, file=["search/index.html", "search/1", "search/2", "search/3", "search/4"]):
    R = 3       # Number of concurrent curl experiments
    S = 0       # Time to sleep waiting for curl
    T = 30      # Time to run experiment
    mtu = 1500  # Max transmission unit
    net = setup(bandwidth=bandwidth, rtt=rtt)
    h1 = net.get('h1')
    h2 = net.get('h2')
    times = []
    modify_route(h1, initcwnd, initrwnd, mtu)
    modify_route(h2, initcwnd, initrwnd, mtu)
    print "H1 route:", h1.cmd("ip route show").strip()
    print "H2 route:", h2.cmd("ip route show").strip()
    Run_Server(net)
    # Measure latency
    start_time = time()
    while True:
        for i in range(R):
            etime = 0
            for q in file:
                cmd = "curl -o /dev/null -s -w %{time_total} " + \
                    h1.IP() + "/http/" + q
                result = h2.cmd(cmd)
                print result
                etime += float(result)
            times += [etime]
        sleep(S)
        now = time()
        delta = now - start_time
        if delta > T:
            break
        print "%.1fs left..." % (T - delta)
    clean(net)
    return np.mean(times)


def FIGURES(name, xaxis, xlabels, title, results):
    N, M = np.shape(results)
    abs_im = []
    per_im = []
    for i in range(N):
        a, b = results[i, :]
        abs_im += [(a - b) * 1000.0]
        per_im += [(a -b)*100 /a] #[(a / b - 1) * 100]
    ind = np.arange(N) 
    width = 0.35 
    fig, ax = plt.subplots()
    rects1 = ax.bar(ind, abs_im, width, color='r')
    for r in rects1:
        r.set_color('#800000')
    ax.set_ylim([1, 10000])
    ax.set_yscale('log')
    ax.set_ylabel('Improvement (ms)')
    ax.set_xlabel(xaxis)
    ax.set_title(title)
    ax.set_xticks(ind + width / 2)
    ax.set_xticklabels(xlabels)
    ax2 = ax.twinx()
    ax2.set_ylim([0, 50.0])
    rects2 = ax2.bar(ind + width, per_im, width, color='y')
    for r in rects2:
        r.set_color('#000066')
    ax.legend((rects1[0], rects2[0]),
              ('Absolute Improvement', 'Percentage Improvement'))

    def autolabel(rects):
        for rect in rects:
            height = rect.get_height()
            ax.text(rect.get_x() + rect.get_width() / 2., 1.05 * height,
                    '%d' % int(height),
                    ha='center', va='bottom')
    fig.savefig('results/' + name + '.png')
    plt.close(fig)

def bw_experiment():
    BW = (256, 512, 1000, 2000, 3000, 5000, 10000, 20000, 50000, 100000, 200000)
    MODE = ((3, 100),(42, 100))
    N = len(BW)
    M = len(MODE)
    RTT = 70
    results = np.zeros((N, 2))
    for r in range(N):
        for i in range(M):
            initcwnd, initrwnd = MODE[i]
            results[r, i] = experiment(BW[r] / 1000.0,
                                       RTT,
                                       initcwnd,
                                       initrwnd)
            print results
    print "Final results"
    print results
    FIGURES("Figure5_BW_42Init",
                     'Bandwidth (Kbps)',
                     BW,
                     '',
                     results)


def bdp_experiment():
    BW = (1000, 5000, 10000, 50000, 100000, 200000)
    MODE = ((3, 100),(42, 100))
    N = len(BW)
    M = len(MODE)
    RTT = 70
    RTT_sec = (RTT / 1000.0)
    results = np.zeros((N, 2))
    for r in range(N):
        for i in range(M):
            initcwnd, initrwnd = MODE[i]
            bandwidth = ((BW[r] * 8) / RTT_sec) / 1000.0
            results[r, i] = experiment(bandwidth / 1000.0,
                                       RTT,
                                       initcwnd,
                                       initrwnd)
            print results

    print "Final results"
    print results
    FIGURES("Figure5_BDP_42Init",
                     'BDP (Bytes)',
                     BW,
                     '',
                     results)


def rtt_experiment():
    RTT = (20, 50, 100, 200, 500, 1000)
    MODE = ((3, 100),(42, 100))
    M = len(MODE)
    N = len(RTT)
    bandwidth = 1.2
    results = np.zeros((N, 2))
    for r in range(N):
        for i in range(M):
            initcwnd, initrwnd = MODE[i]
            results[r, i] = experiment(bandwidth, RTT[r], initcwnd, initrwnd)
            print results
    print "Final results"
    print results
    FIGURES("Figure5_RTT_42Init",
                     'RTT (msec)',
                     RTT,
                     '',
                     results)


if __name__ == "__main__":

    # Setup
    if not os.path.exists("results"):
        os.makedirs("results")

    bw_experiment()
    bdp_experiment()
    rtt_experiment()
