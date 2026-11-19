#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: LIVE 2x2 radio: Sender (laptop, bladeRF-cli)
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
import demo_5_live_sender_player as player  # embedded python block
import sip



class demo_5_live_sender(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "LIVE 2x2 radio: Sender (laptop, bladeRF-cli)", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("LIVE 2x2 radio: Sender (laptop, bladeRF-cli)")
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

        self.settings = Qt.QSettings("GNU Radio", "demo_5_live_sender")

        try:
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
        except BaseException as exc:
            print(f"Qt GUI: Could not restore geometry: {str(exc)}", file=sys.stderr)

        ##################################################
        # Variables
        ##################################################
        self.tx_on = tx_on = 0
        self.howto = howto = "Sender laptop: press Start to loop the stored 2x2 waveform (each run is 50 s). Press again to stop after the current run."
        self.gain = gain = 30

        ##################################################
        # Blocks
        ##################################################

        _tx_on_check_box = Qt.QCheckBox("Transmit")
        self._tx_on_choices = {True: 1, False: 0}
        self._tx_on_choices_inv = dict((v,k) for k,v in self._tx_on_choices.items())
        self._tx_on_callback = lambda i: Qt.QMetaObject.invokeMethod(_tx_on_check_box, "setChecked", Qt.Q_ARG("bool", self._tx_on_choices_inv[i]))
        self._tx_on_callback(self.tx_on)
        _tx_on_check_box.stateChanged.connect(lambda i: self.set_tx_on(self._tx_on_choices[bool(i)]))
        self.top_grid_layout.addWidget(_tx_on_check_box, 2, 0, 1, 2)
        for r in range(2, 3):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 2):
            self.top_grid_layout.setColumnStretch(c, 1)
        self._gain_range = qtgui.Range(0, 60, 1, 30, 200)
        self._gain_win = qtgui.RangeWidget(self._gain_range, self.set_gain, "Transmit gain (dB)", "counter_slider", int, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._gain_win, 1, 0, 1, 2)
        for r in range(1, 2):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 2):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.readout = qtgui.number_sink(
            gr.sizeof_float,
            0,
            qtgui.NUM_GRAPH_NONE,
            3,
            None # parent
        )
        self.readout.set_update_time(0.3)
        self.readout.set_title("Sender")

        labels = ["Runs finished", "Runs cut short (USB drop)", "Transmitting (1 = yes)", '', '',
            '', '', '', '', '']
        units = ["", "", "", '', '',
            '', '', '', '', '']
        colors = [("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"),
            ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black")]
        factor = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]

        for i in range(3):
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
        self.top_grid_layout.addWidget(self._readout_win, 3, 0, 2, 2)
        for r in range(3, 5):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 2):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.player = player.blk(gain=gain, run=tx_on, script="~/txfiles/tx.sh")
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
        self.connect((self.player, 1), (self.readout, 1))
        self.connect((self.player, 0), (self.readout, 0))
        self.connect((self.player, 2), (self.readout, 2))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("GNU Radio", "demo_5_live_sender")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_tx_on(self):
        return self.tx_on

    def set_tx_on(self, tx_on):
        self.tx_on = tx_on
        self._tx_on_callback(self.tx_on)
        self.player.run = self.tx_on

    def get_howto(self):
        return self.howto

    def set_howto(self, howto):
        self.howto = howto
        Qt.QMetaObject.invokeMethod(self._howto_label, "setText", Qt.Q_ARG("QString", str(self._howto_formatter(self.howto))))

    def get_gain(self):
        return self.gain

    def set_gain(self, gain):
        self.gain = gain
        self.player.gain = self.gain




def main(top_block_cls=demo_5_live_sender, options=None):

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
