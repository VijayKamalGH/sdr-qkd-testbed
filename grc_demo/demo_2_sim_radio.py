#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Spatial-qubit BB84 over a simulated 2x2 radio
# GNU Radio version: 3.10.9.2

from PyQt5 import Qt
from gnuradio import qtgui
from PyQt5 import QtCore
from gnuradio import analog
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
import demo_2_sim_radio_receiver as receiver  # embedded python block
import demo_2_sim_radio_sender as sender  # embedded python block
import numpy as np
import sip



class demo_2_sim_radio(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "Spatial-qubit BB84 over a simulated 2x2 radio", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Spatial-qubit BB84 over a simulated 2x2 radio")
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

        self.settings = Qt.QSettings("GNU Radio", "demo_2_sim_radio")

        try:
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
        except BaseException as exc:
            print(f"Qt GUI: Could not restore geometry: {str(exc)}", file=sys.stderr)

        ##################################################
        # Variables
        ##################################################
        self.phase = phase = 40
        self.mix = mix = 0.35
        self.samp_rate = samp_rate = 2000000
        self.reset = reset = 0
        self.noise = noise = 0.2
        self.howto = howto = "Sender (TX1, TX2) -> 2x2 channel + noise -> Receiver. Move the sliders; press New session after each change."
        self.h11 = h11 = 0.9*np.exp(0.7j)
        self.h10 = h10 = 0.85*mix*np.exp(1j*np.deg2rad(phase+70))
        self.h01 = h01 = mix*np.exp(1j*np.deg2rad(phase))
        self.h00 = h00 = 1
        self.eve_rate = eve_rate = 0
        self.cfo = cfo = 500

        ##################################################
        # Blocks
        ##################################################

        _reset_push_button = Qt.QPushButton("New session")
        _reset_push_button = Qt.QPushButton("New session")
        self._reset_choices = {'Pressed': 1, 'Released': 0}
        _reset_push_button.pressed.connect(lambda: self.set_reset(self._reset_choices['Pressed']))
        _reset_push_button.released.connect(lambda: self.set_reset(self._reset_choices['Released']))
        self.top_grid_layout.addWidget(_reset_push_button, 3, 2, 1, 2)
        for r in range(3, 4):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(2, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        self._noise_range = qtgui.Range(0, 1.5, 0.02, 0.2, 200)
        self._noise_win = qtgui.RangeWidget(self._noise_range, self.set_noise, "Receiver noise level", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._noise_win, 1, 2, 1, 2)
        for r in range(1, 2):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(2, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        self._eve_rate_range = qtgui.Range(0, 1, 0.05, 0, 200)
        self._eve_rate_win = qtgui.RangeWidget(self._eve_rate_range, self.set_eve_rate, "Eavesdropper: share of qubits intercepted", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._eve_rate_win, 1, 0, 1, 2)
        for r in range(1, 2):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 2):
            self.top_grid_layout.setColumnStretch(c, 1)
        self._cfo_range = qtgui.Range(-2000, 2000, 50, 500, 200)
        self._cfo_win = qtgui.RangeWidget(self._cfo_range, self.set_cfo, "Carrier offset between radios (Hz)", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._cfo_win, 3, 0, 1, 2)
        for r in range(3, 4):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 2):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.tx_scope = qtgui.time_sink_f(
            96000, #size
            samp_rate, #samp_rate
            "Sender: one frame, TX1 (A) and TX2 (B)  [pilot A | pilot B | index | 272 qubits | guard]", #name
            2, #number of inputs
            None # parent
        )
        self.tx_scope.set_update_time(0.5)
        self.tx_scope.set_y_axis(-1, 1)

        self.tx_scope.set_y_label('Amplitude', "")

        self.tx_scope.enable_tags(True)
        self.tx_scope.set_trigger_mode(qtgui.TRIG_MODE_FREE, qtgui.TRIG_SLOPE_POS, 0.0, 0, 0, "")
        self.tx_scope.enable_autoscale(True)
        self.tx_scope.enable_grid(False)
        self.tx_scope.enable_axis_labels(True)
        self.tx_scope.enable_control_panel(False)
        self.tx_scope.enable_stem_plot(False)


        labels = ["TX1 (stream A)", "TX2 (stream B)", 'Signal 3', 'Signal 4', 'Signal 5',
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
                self.tx_scope.set_line_label(i, "Data {0}".format(i))
            else:
                self.tx_scope.set_line_label(i, labels[i])
            self.tx_scope.set_line_width(i, widths[i])
            self.tx_scope.set_line_color(i, colors[i])
            self.tx_scope.set_line_style(i, styles[i])
            self.tx_scope.set_line_marker(i, markers[i])
            self.tx_scope.set_line_alpha(i, alphas[i])

        self._tx_scope_win = sip.wrapinstance(self.tx_scope.qwidget(), Qt.QWidget)
        self.top_grid_layout.addWidget(self._tx_scope_win, 7, 0, 2, 4)
        for r in range(7, 9):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.thr1 = blocks.throttle(gr.sizeof_gr_complex*1, samp_rate,True)
        self.thr0 = blocks.throttle(gr.sizeof_gr_complex*1, samp_rate,True)
        self.sum1 = blocks.add_vcc(1)
        self.sum0 = blocks.add_vcc(1)
        self.sender = sender.blk(seed=20261030, amplitude=0.14, eve_rate=eve_rate)
        self.rx_scope = qtgui.time_sink_f(
            96000, #size
            samp_rate, #samp_rate
            "Receiver antennas RX0 / RX1 (after channel + noise)", #name
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
        self.top_grid_layout.addWidget(self._rx_scope_win, 9, 0, 2, 4)
        for r in range(9, 11):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.rx1 = blocks.add_vcc(1)
        self.rx0 = blocks.add_vcc(1)
        self.receiver = receiver.blk(seed=20261030, receiver_seed=777, batch_frames=40, key_frames=200, skip_first=0, reset=reset)
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
        self.re_b = blocks.complex_to_real(1)
        self.re_a = blocks.complex_to_real(1)
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
        self._phase_range = qtgui.Range(0, 180, 5, 40, 200)
        self._phase_win = qtgui.RangeWidget(self._phase_range, self.set_phase, "Cross-talk phase (deg)", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._phase_win, 2, 2, 1, 2)
        for r in range(2, 3):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(2, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.n1 = analog.noise_source_c(analog.GR_GAUSSIAN, noise, 2)
        self.n0 = analog.noise_source_c(analog.GR_GAUSSIAN, noise, 1)
        self._mix_range = qtgui.Range(0, 0.9, 0.05, 0.35, 200)
        self._mix_win = qtgui.RangeWidget(self._mix_range, self.set_mix, "Cross-talk between the two antennas", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._mix_win, 2, 0, 1, 2)
        for r in range(2, 3):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 2):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.lo = analog.sig_source_c(samp_rate, analog.GR_COS_WAVE, cfo, 1, 0, 0)
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
        self.g11 = blocks.multiply_const_cc(h11)
        self.g10 = blocks.multiply_const_cc(h10)
        self.g01 = blocks.multiply_const_cc(h01)
        self.g00 = blocks.multiply_const_cc(h00)
        self.cfo1 = blocks.multiply_vcc(1)
        self.cfo0 = blocks.multiply_vcc(1)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.cfo0, 0), (self.re_r0, 0))
        self.connect((self.cfo0, 0), (self.receiver, 0))
        self.connect((self.cfo1, 0), (self.re_r1, 0))
        self.connect((self.cfo1, 0), (self.receiver, 1))
        self.connect((self.g00, 0), (self.sum0, 0))
        self.connect((self.g01, 0), (self.sum0, 1))
        self.connect((self.g10, 0), (self.sum1, 0))
        self.connect((self.g11, 0), (self.sum1, 1))
        self.connect((self.lo, 0), (self.cfo0, 1))
        self.connect((self.lo, 0), (self.cfo1, 1))
        self.connect((self.n0, 0), (self.rx0, 1))
        self.connect((self.n1, 0), (self.rx1, 1))
        self.connect((self.re_a, 0), (self.tx_scope, 0))
        self.connect((self.re_b, 0), (self.tx_scope, 1))
        self.connect((self.re_r0, 0), (self.rx_scope, 0))
        self.connect((self.re_r1, 0), (self.rx_scope, 1))
        self.connect((self.receiver, 0), (self.qubit_plane, 0))
        self.connect((self.receiver, 7), (self.readout, 6))
        self.connect((self.receiver, 4), (self.readout, 3))
        self.connect((self.receiver, 6), (self.readout, 5))
        self.connect((self.receiver, 3), (self.readout, 2))
        self.connect((self.receiver, 1), (self.readout, 0))
        self.connect((self.receiver, 5), (self.readout, 4))
        self.connect((self.receiver, 2), (self.readout, 1))
        self.connect((self.rx0, 0), (self.cfo0, 0))
        self.connect((self.rx1, 0), (self.cfo1, 0))
        self.connect((self.sender, 0), (self.thr0, 0))
        self.connect((self.sender, 1), (self.thr1, 0))
        self.connect((self.sum0, 0), (self.rx0, 0))
        self.connect((self.sum1, 0), (self.rx1, 0))
        self.connect((self.thr0, 0), (self.g00, 0))
        self.connect((self.thr0, 0), (self.g10, 0))
        self.connect((self.thr0, 0), (self.re_a, 0))
        self.connect((self.thr1, 0), (self.g01, 0))
        self.connect((self.thr1, 0), (self.g11, 0))
        self.connect((self.thr1, 0), (self.re_b, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("GNU Radio", "demo_2_sim_radio")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_phase(self):
        return self.phase

    def set_phase(self, phase):
        self.phase = phase
        self.set_h01(self.mix*np.exp(1j*np.deg2rad(self.phase)))
        self.set_h10(0.85*self.mix*np.exp(1j*np.deg2rad(self.phase+70)))

    def get_mix(self):
        return self.mix

    def set_mix(self, mix):
        self.mix = mix
        self.set_h01(self.mix*np.exp(1j*np.deg2rad(self.phase)))
        self.set_h10(0.85*self.mix*np.exp(1j*np.deg2rad(self.phase+70)))

    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate
        self.lo.set_sampling_freq(self.samp_rate)
        self.rx_scope.set_samp_rate(self.samp_rate)
        self.thr0.set_sample_rate(self.samp_rate)
        self.thr1.set_sample_rate(self.samp_rate)
        self.tx_scope.set_samp_rate(self.samp_rate)

    def get_reset(self):
        return self.reset

    def set_reset(self, reset):
        self.reset = reset
        self.receiver.reset = self.reset

    def get_noise(self):
        return self.noise

    def set_noise(self, noise):
        self.noise = noise
        self.n0.set_amplitude(self.noise)
        self.n1.set_amplitude(self.noise)

    def get_howto(self):
        return self.howto

    def set_howto(self, howto):
        self.howto = howto
        Qt.QMetaObject.invokeMethod(self._howto_label, "setText", Qt.Q_ARG("QString", str(self._howto_formatter(self.howto))))

    def get_h11(self):
        return self.h11

    def set_h11(self, h11):
        self.h11 = h11
        self.g11.set_k(self.h11)

    def get_h10(self):
        return self.h10

    def set_h10(self, h10):
        self.h10 = h10
        self.g10.set_k(self.h10)

    def get_h01(self):
        return self.h01

    def set_h01(self, h01):
        self.h01 = h01
        self.g01.set_k(self.h01)

    def get_h00(self):
        return self.h00

    def set_h00(self, h00):
        self.h00 = h00
        self.g00.set_k(self.h00)

    def get_eve_rate(self):
        return self.eve_rate

    def set_eve_rate(self, eve_rate):
        self.eve_rate = eve_rate
        self.sender.eve_rate = self.eve_rate

    def get_cfo(self):
        return self.cfo

    def set_cfo(self, cfo):
        self.cfo = cfo
        self.lo.set_frequency(self.cfo)




def main(top_block_cls=demo_2_sim_radio, options=None):

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
