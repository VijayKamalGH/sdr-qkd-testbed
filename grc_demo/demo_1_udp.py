#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Public channel over UDP (run on both laptops)
# GNU Radio version: 3.10.9.2

from PyQt5 import Qt
from gnuradio import qtgui
from PyQt5 import QtCore
from PyQt5.QtCore import QObject, pyqtSlot
from gnuradio import eng_notation
from gnuradio import gr
from gnuradio.filter import firdes
from gnuradio.fft import window
import sys
import signal
from PyQt5 import Qt
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
import demo_1_udp_udp as udp  # embedded python block
import sip



class demo_1_udp(gr.top_block, Qt.QWidget):

    def __init__(self):
        gr.top_block.__init__(self, "Public channel over UDP (run on both laptops)", catch_exceptions=True)
        Qt.QWidget.__init__(self)
        self.setWindowTitle("Public channel over UDP (run on both laptops)")
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

        self.settings = Qt.QSettings("GNU Radio", "demo_1_udp")

        try:
            geometry = self.settings.value("geometry")
            if geometry:
                self.restoreGeometry(geometry)
        except BaseException as exc:
            print(f"Qt GUI: Could not restore geometry: {str(exc)}", file=sys.stderr)

        ##################################################
        # Variables
        ##################################################
        self.role = role = "receiver"
        self.qch = qch = 0.02
        self.q_eve = q_eve = 0
        self.peer = peer = "127.0.0.1:5006"
        self.p_loss = p_loss = 0
        self.howto = howto = "Run this on BOTH laptops: one Sender, one Receiver. Start the Receiver first, then press Start on both."
        self.go = go = 0

        ##################################################
        # Blocks
        ##################################################

        # Create the options list
        self._role_options = ['receiver', 'sender']
        # Create the labels list
        self._role_labels = ['Receiver', 'Sender']
        # Create the combo box
        self._role_tool_bar = Qt.QToolBar(self)
        self._role_tool_bar.addWidget(Qt.QLabel("This laptop is" + ": "))
        self._role_combo_box = Qt.QComboBox()
        self._role_tool_bar.addWidget(self._role_combo_box)
        for _label in self._role_labels: self._role_combo_box.addItem(_label)
        self._role_callback = lambda i: Qt.QMetaObject.invokeMethod(self._role_combo_box, "setCurrentIndex", Qt.Q_ARG("int", self._role_options.index(i)))
        self._role_callback(self.role)
        self._role_combo_box.currentIndexChanged.connect(
            lambda i: self.set_role(self._role_options[i]))
        # Create the radio buttons
        self.top_grid_layout.addWidget(self._role_tool_bar, 1, 0, 1, 2)
        for r in range(1, 2):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 2):
            self.top_grid_layout.setColumnStretch(c, 1)
        self._qch_range = qtgui.Range(0, 0.2, 0.01, 0.02, 200)
        self._qch_win = qtgui.RangeWidget(self._qch_range, self.set_qch, "Channel disturbance (QBER)", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._qch_win, 3, 0, 1, 2)
        for r in range(3, 4):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 2):
            self.top_grid_layout.setColumnStretch(c, 1)
        self._q_eve_range = qtgui.Range(0, 1, 0.25, 0, 200)
        self._q_eve_win = qtgui.RangeWidget(self._q_eve_range, self.set_q_eve, "Eavesdropper: share of qubits intercepted", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._q_eve_win, 2, 0, 1, 2)
        for r in range(2, 3):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 2):
            self.top_grid_layout.setColumnStretch(c, 1)
        self._peer_tool_bar = Qt.QToolBar(self)
        self._peer_tool_bar.addWidget(Qt.QLabel("Other laptop IP:port" + ": "))
        self._peer_line_edit = Qt.QLineEdit(str(self.peer))
        self._peer_tool_bar.addWidget(self._peer_line_edit)
        self._peer_line_edit.editingFinished.connect(
            lambda: self.set_peer(str(str(self._peer_line_edit.text()))))
        self.top_grid_layout.addWidget(self._peer_tool_bar, 1, 2, 1, 2)
        for r in range(1, 2):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(2, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        self._p_loss_range = qtgui.Range(0, 0.3, 0.01, 0, 200)
        self._p_loss_win = qtgui.RangeWidget(self._p_loss_range, self.set_p_loss, "Frame loss (Receiver side)", "counter_slider", float, QtCore.Qt.Horizontal)
        self.top_grid_layout.addWidget(self._p_loss_win, 2, 2, 1, 2)
        for r in range(2, 3):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(2, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        _go_push_button = Qt.QPushButton("Start")
        _go_push_button = Qt.QPushButton("Start")
        self._go_choices = {'Pressed': 1, 'Released': 0}
        _go_push_button.pressed.connect(lambda: self.set_go(self._go_choices['Pressed']))
        _go_push_button.released.connect(lambda: self.set_go(self._go_choices['Released']))
        self.top_grid_layout.addWidget(_go_push_button, 3, 2, 1, 2)
        for r in range(3, 4):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(2, 4):
            self.top_grid_layout.setColumnStretch(c, 1)
        self.udp = udp.blk(role=role, peer=peer, listen=5005 if role == 'receiver' else 5006, n=40000, qch=qch, q_eve=q_eve, p_loss=p_loss, go=go)
        self.readout = qtgui.number_sink(
            gr.sizeof_float,
            0,
            qtgui.NUM_GRAPH_NONE,
            5,
            None # parent
        )
        self.readout.set_update_time(0.3)
        self.readout.set_title("Result (same on both laptops when no abort)")

        labels = ["Estimated QBER", "Secret key", "Frames sent", "Frames lost / resent", "Status (1 running, 2 key, 3 abort)",
            '', '', '', '', '']
        units = ["%", "bits", "", "", "",
            '', '', '', '', '']
        colors = [("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"),
            ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black"), ("black", "black")]
        factor = [1, 1, 1, 1, 1,
            1, 1, 1, 1, 1]

        for i in range(5):
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
        self.top_grid_layout.addWidget(self._readout_win, 4, 0, 3, 4)
        for r in range(4, 7):
            self.top_grid_layout.setRowStretch(r, 1)
        for c in range(0, 4):
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
        self.connect((self.udp, 1), (self.readout, 1))
        self.connect((self.udp, 4), (self.readout, 4))
        self.connect((self.udp, 2), (self.readout, 2))
        self.connect((self.udp, 3), (self.readout, 3))
        self.connect((self.udp, 0), (self.readout, 0))


    def closeEvent(self, event):
        self.settings = Qt.QSettings("GNU Radio", "demo_1_udp")
        self.settings.setValue("geometry", self.saveGeometry())
        self.stop()
        self.wait()

        event.accept()

    def get_role(self):
        return self.role

    def set_role(self, role):
        self.role = role
        self._role_callback(self.role)
        self.udp.listen = 5005 if self.role == 'receiver' else 5006
        self.udp.role = self.role

    def get_qch(self):
        return self.qch

    def set_qch(self, qch):
        self.qch = qch
        self.udp.qch = self.qch

    def get_q_eve(self):
        return self.q_eve

    def set_q_eve(self, q_eve):
        self.q_eve = q_eve
        self.udp.q_eve = self.q_eve

    def get_peer(self):
        return self.peer

    def set_peer(self, peer):
        self.peer = peer
        Qt.QMetaObject.invokeMethod(self._peer_line_edit, "setText", Qt.Q_ARG("QString", str(self.peer)))
        self.udp.peer = self.peer

    def get_p_loss(self):
        return self.p_loss

    def set_p_loss(self, p_loss):
        self.p_loss = p_loss
        self.udp.p_loss = self.p_loss

    def get_howto(self):
        return self.howto

    def set_howto(self, howto):
        self.howto = howto
        Qt.QMetaObject.invokeMethod(self._howto_label, "setText", Qt.Q_ARG("QString", str(self._howto_formatter(self.howto))))

    def get_go(self):
        return self.go

    def set_go(self, go):
        self.go = go
        self.udp.go = self.go




def main(top_block_cls=demo_1_udp, options=None):

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
