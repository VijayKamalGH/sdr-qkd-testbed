#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Fresh-sweep results (W1 / W2)
# GNU Radio version: 3.10.9.2

from PyQt5 import Qt
from gnuradio import qtgui
from PyQt5 import QtCore
from gnuradio import eng_notation
from gnuradio import gr
from gnuradio.filter import firdes
from gnuradio.fft import window
import sys
import signal
from PyQt5 import Qt
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
import demo_3_sweep_table_table as table  # embedded python block
import sip



class demo_3_sweep_table(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "Fresh-sweep results (W1 / W2)", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Fresh-sweep results (W1 / W2)")
        qtgui.util.check_set_qss()
        try:
            self.setWindowIcon(Qt.QIcon.fromTheme('gnuradio-grc'))
        except BaseException as exc:
            print(f"Qt GUI: Could not set Icon: {str(exc)}", file=sys.stderr)
        self.top_scroll_layout = Qt.QVBoxLayout()
        self.setLayout(self.top_scroll_layout)
        self.top_scroll = Qt.QScrollArea()
        self.top_scroll.setFrameStyle(Qt.QFrame.NoFrame)
        self.top_scroll_layout.addWidget(self.top_scroll)
        self.top_scroll.setWidgetResizable(True)
        self.top_widget = Qt.QWidget()
        self.top_scroll.setWidget(self.top_widget)
        self.top_layout = Qt.QVBoxLayout(self.top_widget)
        self.top_grid_layout = Qt.QGridLayout()
        self.top_layout.addLayout(self.top_grid_layout)

        self.settings = Qt.QSettings("GNU Radio", "demo_3_sweep_table")

        try:
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
        except BaseException as exc:
            print(f"Qt GUI: Could not restore geometry: {str(exc)}", file=sys.stderr)

        ##################################################
        # Variables
        ##################################################
        self.which = which = 0
        self.howto = howto = "Pick a stored capture: transmit gain, SINR, QBER and key length with the MMSE and ZF detectors."

        ##################################################
        # Blocks
        ##################################################

        self._which_range = qtgui.Range(0, 30, 1, 0, 200)
        self._which_win = qtgui.RangeWidget(self._which_range, self.set_which, "Capture number (0 to 30; 0-16 = W1, 17-30 = W2)", "counter_slider", int, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._which_win, 1, 0, 1, 2)
        for r in range(1, 2):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 2):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.table = table.blk(idx=which, table="w1w2_table.json")
        self.readout = qtgui.number_sink(
            gr.sizeof_float,
            0,
            qtgui.NUM_GRAPH_NONE,
            7,
            None # parent
        )
        self.readout.set_update_time(0.3)
        self.readout.set_title("Stored result")

        labels = ["Capture tag (SWW...)", "TX gain", "SINR", "QBER (MMSE)", "QBER (ZF)",
            "Key (MMSE)", "Key (ZF)", '', '', '']
        units = ["", "dB", "dB", "%", "%",
            "bits", "bits", '', '', '']
        colors = [("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"),
            ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black")]
        factor = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]

        for i in range(7):
            self.readout.set_min(i, 0)
            self.readout.set_max(i, 100)
            self.readout.set_color(i, colors[i][0], colors[i][1])
            if len(labels[i]) == 0:
                self.readout.set_label(i, "Data {0}".format(i))
            else:
                self.readout.set_label(i, labels[i])
            self.readout.set_unit(i, units[i])
            self.readout.set_factor(i, factor[i])

        self.readout.enable_autoscale(False)
        self._readout_win = sip.wrapinstance(self.readout.qwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._readout_win, 2, 0, 3, 2)
        for r in range(2, 5):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 2):
            self.top_grid_layout.setColumnStretch(c, 1)
        self._howto_tool_bar = Qt.QToolBar(self)

        if None:
            self._howto_formatter = None
        else:
            self._howto_formatter = lambda x: str(x)

        self._howto_tool_bar.addWidget(Qt.QLabel("How it works"))
        self._howto_label = Qt.QLabel(str(self._howto_formatter(self.howto)))
        self._howto_tool_bar.addWidget(self._howto_label)
        self.top_grid_layout.addWidget(self._howto_tool_bar, 0, 0, 1, 2)
        for r in range(0, 1):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 2):
            self.top_grid_layout.setColumnStretch(c, 1)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.table, 2), (self.readout, 2))
        self.connect((self.table, 0), (self.readout, 0))
        self.connect((self.table, 4), (self.readout, 4))
        self.connect((self.table, 1), (self.readout, 1))
        self.connect((self.table, 3), (self.readout, 3))
        self.connect((self.table, 5), (self.readout, 5))
        self.connect((self.table, 6), (self.readout, 6))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("GNU Radio", "demo_3_sweep_table")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_which(self):
        return self.which

    def set_which(self, which):
        self.which = which
        self.table.idx = self.which

    def get_howto(self):
        return self.howto

    def set_howto(self, howto):
        self.howto = howto
        Qt.QMetaObject.invokeMethod(self._howto_label, "setText", Qt.Q_ARG("QString", str(self._howto_formatter(self.howto))))




def main(top_block_cls=demo_3_sweep_table, options=None):

    qapp = Qt.QApplication(sys.argv)

    tb = top_block_cls()

    tb.start()

    tb.show()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        Qt.QApplication.quit()

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    timer = Qt.QTimer()
    timer.start(500)
    timer.timeout.connect(lambda: None)

    qapp.exec_()

if __name__ == '__main__':
    main()
