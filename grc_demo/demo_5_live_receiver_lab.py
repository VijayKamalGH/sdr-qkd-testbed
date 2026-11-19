# LAB-MATCHED variant of demo_5_live_receiver: the radio is configured exactly like H194E_BB84_RF_DUAL_CAPTURE_V4.py
# (sample rate, centre frequency, bandwidth, manual gain only; no IF/BB gain, DC or I/Q-balance calls).
# GRC overwrites demo_5_live_receiver.py every time it runs; this file is not touched.
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: LIVE 2x2 radio: Receiver (bladeRF RX0 + RX1)
# GNU Radio version: 3.10.9.2

from PyQt5 import Qt
from gnuradio import qtgui
from PyQt5 import QtCore
from gnuradio import blocks
from gnuradio import eng_notation
from gnuradio import gr
from gnuradio.filter import firdes
from gnuradio.fft import window
import sys
import signal
from PyQt5 import Qt
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
import demo_5_live_receiver_receiver as receiver  # embedded python block
import osmosdr
import time
import sip



class demo_5_live_receiver(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "LIVE 2x2 radio: Receiver (bladeRF RX0 + RX1)", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("LIVE 2x2 radio: Receiver (bladeRF RX0 + RX1)")
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

        self.settings = Qt.QSettings("GNU Radio", "demo_5_live_receiver")

        try:
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
        except BaseException as exc:
            print(f"Qt GUI: Could not restore geometry: {str(exc)}", file=sys.stderr)

        ##################################################
        # Variables
        ##################################################
        self.samp_rate = samp_rate = 2000000
        self.reset = reset = 0
        self.howto = howto = "Radios warmed up ~20 min. Start the Sender first. This window then decodes the live link frame by frame."
        self.gain1 = gain1 = 30
        self.gain0 = gain0 = 20

        ##################################################
        # Blocks
        ##################################################

        _reset_push_button = Qt.QPushButton("New session")
        _reset_push_button = Qt.QPushButton("New session")
        self._reset_choices = {'Pressed': 1, 'Released': 0}
        _reset_push_button.pressed.connect(lambda: self.set_reset(self._reset_choices['Pressed']))
        _reset_push_button.released.connect(lambda: self.set_reset(self._reset_choices['Released']))
        self.top_grid_layout.addWidget(_reset_push_button, 2, 0, 1, 4)
        for r in range(2, 3):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        self._gain1_range = qtgui.Range(0, 60, 1, 30, 200)
        self._gain1_win = qtgui.RangeWidget(self._gain1_range, self.set_gain1, "RX1 gain (dB)", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._gain1_win, 1, 2, 1, 2)
        for r in range(1, 2):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(2, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        self._gain0_range = qtgui.Range(0, 60, 1, 20, 200)
        self._gain0_win = qtgui.RangeWidget(self._gain0_range, self.set_gain0, "RX0 gain (dB)", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._gain0_win, 1, 0, 1, 2)
        for r in range(1, 2):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 2):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.rx_scope = qtgui.time_sink_f(
            96000, #size
            samp_rate, #samp_rate
            "Receiver antennas RX0 / RX1 (frames: pilots, index, qubits, guard)", #name
            2, #number of inputs
            None # parent
        )
        self.rx_scope.set_update_time(0.5)
        self.rx_scope.set_y_axis(-1, 1)

        self.rx_scope.set_y_label('Amplitude', "")

        self.rx_scope.enable_tags(True)
        self.rx_scope.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.rx_scope.enable_autoscale(True)
        self.rx_scope.enable_grid(False)
        self.rx_scope.enable_axis_labels(True)
        self.rx_scope.enable_control_panel(False)
        self.rx_scope.enable_stem_plot(False)


        labels = ["RX0", "RX1", 'Signal 3', 'Signal 4', 'Signal 5',
            'Signal 6', 'Signal 7', 'Signal 8', 'Signal 9', 'Signal 10']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ['blue', 'red', 'green', 'black', 'cyan',
            'magenta', 'yellow', 'dark red', 'dark green', 'dark blue']
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]
        styles = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        markers = [-1, -1, -1, -1, -1,
            -1, -1, -1, -1, -1]


        for i in range(2):
            if len(labels[i]) == 0:
                self.rx_scope.set_line_label(i, "Data {0}".format(i))
            else:
                self.rx_scope.set_line_label(i, labels[i])
            self.rx_scope.set_line_width(i, widths[i])
            self.rx_scope.set_line_color(i, colors[i])
            self.rx_scope.set_line_style(i, styles[i])
            self.rx_scope.set_line_marker(i, markers[i])
            self.rx_scope.set_line_alpha(i, alphas[i])

        self._rx_scope_win = sip.wrapinstance(self.rx_scope.qwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._rx_scope_win, 7, 0, 2, 4)
        for r in range(7, 9):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.receiver = receiver.blk(seed=20261030, receiver_seed=777, batch_frames=40, key_frames=200, skip_first=200000, reset=reset, detector="MMSE", threaded=1)
        self.readout = qtgui.number_sink(
            gr.sizeof_float,
            0,
            qtgui.NUM_GRAPH_NONE,
            7,
            None # parent
        )
        self.readout.set_update_time(0.3)
        self.readout.set_title("Result")

        labels = ["QBER", "Q_upper (abort if > 11)", "SINR stream A", "SINR stream B", "Secret key",
            "Frames decoded", "Status (0 busy, 1 key, 2 abort)", '', '', '']
        units = ["%", "%", "dB", "dB", "bits",
            "", "", '', '', '']
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
        self.top_grid_layout.addWidget(self._readout_win, 4, 2, 3, 2)
        for r in range(4, 7):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(2, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.re_r1 = blocks.complex_to_real(1)
        self.re_r0 = blocks.complex_to_real(1)
        self.radio = osmosdr.source(
            args="numchan=" + str(2) + " " + "numchan=2 bladerf=0,nchan=2"
        )
        self.radio.set_sample_rate(samp_rate)
        self.radio.set_center_freq(915000000, 0)
        self.radio.set_gain_mode(False, 0)
        self.radio.set_gain(gain0, 0)
        self.radio.set_bandwidth(1000000, 0)
        self.radio.set_center_freq(915000000, 1)
        self.radio.set_gain_mode(False, 1)
        self.radio.set_gain(gain1, 1)
        self.radio.set_bandwidth(1000000, 1)
        self.qubit_plane = qtgui.const_sink_c(
            1088, #size
            "Receiver's qubit plane (z1, z2): the four BB84 states (1,0) (0,1) (0.7,0.7) (0.7,-0.7)", #name
            1, #number of inputs
            None # parent
        )
        self.qubit_plane.set_update_time(0.2)
        self.qubit_plane.set_y_axis((-2), 2)
        self.qubit_plane.set_x_axis((-2), 2)
        self.qubit_plane.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, "")
        self.qubit_plane.enable_autoscale(False)
        self.qubit_plane.enable_grid(False)
        self.qubit_plane.enable_axis_labels(True)


        labels = ['', '', '', '', '',
            '', '', '', '', '']
        widths = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]
        colors = ["blue", "red", "green", "black", "cyan",
            "magenta", "yellow", "dark red", "dark green", "dark blue"]
        styles = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        markers = [0, 0, 0, 0, 0,
            0, 0, 0, 0, 0]
        alphas = [1.0, 1.0, 1.0, 1.0, 1.0,
            1.0, 1.0, 1.0, 1.0, 1.0]

        for i in range(1):
            if len(labels[i]) == 0:
                self.qubit_plane.set_line_label(i, "Data {0}".format(i))
            else:
                self.qubit_plane.set_line_label(i, labels[i])
            self.qubit_plane.set_line_width(i, widths[i])
            self.qubit_plane.set_line_color(i, colors[i])
            self.qubit_plane.set_line_style(i, styles[i])
            self.qubit_plane.set_line_marker(i, markers[i])
            self.qubit_plane.set_line_alpha(i, alphas[i])

        self._qubit_plane_win = sip.wrapinstance(self.qubit_plane.qwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._qubit_plane_win, 4, 0, 3, 2)
        for r in range(4, 7):
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
        self.top_grid_layout.addWidget(self._howto_tool_bar, 0, 0, 1, 4)
        for r in range(0, 1):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 4):
            self.top_grid_layout.setColumnStretch(c, 1)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.radio, 0), (self.re_r0, 0))
        self.connect((self.radio, 1), (self.re_r1, 0))
        self.connect((self.radio, 1), (self.receiver, 1))
        self.connect((self.radio, 0), (self.receiver, 0))
        self.connect((self.re_r0, 0), (self.rx_scope, 0))
        self.connect((self.re_r1, 0), (self.rx_scope, 1))
        self.connect((self.receiver, 0), (self.qubit_plane, 0))
        self.connect((self.receiver, 3), (self.readout, 2))
        self.connect((self.receiver, 1), (self.readout, 0))
        self.connect((self.receiver, 5), (self.readout, 4))
        self.connect((self.receiver, 4), (self.readout, 3))
        self.connect((self.receiver, 7), (self.readout, 6))
        self.connect((self.receiver, 6), (self.readout, 5))
        self.connect((self.receiver, 2), (self.readout, 1))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("GNU Radio", "demo_5_live_receiver")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.radio.set_sample_rate(self.samp_rate)
        self.rx_scope.set_samp_rate(self.samp_rate)

    def get_reset(self):
        return self.reset

    def set_reset(self, reset):
        self.reset = reset
        self.receiver.reset = self.reset

    def get_howto(self):
        return self.howto

    def set_howto(self, howto):
        self.howto = howto
        Qt.QMetaObject.invokeMethod(self._howto_label, "setText", Qt.Q_ARG("QString", str(self._howto_formatter(self.howto))))

    def get_gain1(self):
        return self.gain1

    def set_gain1(self, gain1):
        self.gain1 = gain1
        self.radio.set_gain(self.gain1, 1)

    def get_gain0(self):
        return self.gain0

    def set_gain0(self, gain0):
        self.gain0 = gain0
        self.radio.set_gain(self.gain0, 0)




def main(top_block_cls=demo_5_live_receiver, options=None):

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
