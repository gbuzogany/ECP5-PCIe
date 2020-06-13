from nmigen import *
from nmigen.build import *
from serdes import K, D, Ctrl, PCIeSERDESInterface
from layouts import ts_layout

class PCIePhyTX(Elaboratable):
    """
    PCIe Transmitter for 1:2 gearing

    Parameters
    ----------
    lane : PCIeSERDESInterface
        PCIe lane
    ts : Record(ts_layout)
        Data to send
    """
    def __init__(self, lane : PCIeSERDESInterface):
        assert lane.ratio == 2
        self.lane = lane
        self.ts = Record(ts_layout)

    def elaborate(self, platform: Platform) -> Module:
        m = Module()

        lane = self.lane
        ts = self.ts # ts to transmit
        self.start_send_ts = Signal()
        symbol1 = lane.tx_symbol[0: 9]
        symbol2 = lane.tx_symbol[9:18]

        with m.FSM(domain="tx"):
            with m.State("IDLE"):
                with m.If(ts.valid):
                    m.d.tx += lane.tx_e_idle.eq(0b0)
                    m.next = "TSn-LANE-FTS"
                    m.d.tx += [
                        symbol1.eq(Ctrl.COM),
                        lane.tx_set_disp[0].eq(1),
                        lane.tx_disp[0].eq(0),
                        self.start_send_ts.eq(1)
                    ]
                    with m.If(ts.link.valid):
                        m.d.tx += symbol2.eq(Cat(ts.link.number, Signal())) # Hopefully the right order?
                    with m.Else():
                        m.d.tx += symbol2.eq(Ctrl.PAD)
                #with m.Else():
                #    m.d.tx += lane.tx_e_idle.eq(0b11)
            with m.State("TSn-LANE-FTS"):
                m.d.tx += lane.tx_set_disp[0].eq(0)
                m.d.tx += self.start_send_ts.eq(0)
                with m.If(ts.lane.valid):
                    m.d.tx += symbol1.eq(Cat(ts.lane.number, Signal()))
                with m.Else():
                    m.d.tx += symbol1.eq(Ctrl.PAD)
                m.d.tx += symbol2.eq(Cat(ts.n_fts, Signal()))
                m.next = "TSn-DATA"
            with m.State("TSn-DATA"):
                m.d.tx += symbol1.eq(Cat(ts.rate, Signal()))
                m.d.tx += symbol2.eq(Cat(ts.ctrl, Signal(4)))
                m.next = "TSn-ID0"
            for i in range(5):
                with m.State("TSn-ID%d" % i):
                    m.next = "IDLE" if i == 4 else "TSn-ID%d" % (i + 1)
                    with m.If(ts.ts_id == 0):
                        m.d.tx += [
                            symbol1.eq(D(10,2)),
                            symbol2.eq(D(10,2))
                        ]
                    with m.Else():
                        m.d.tx += [
                            symbol1.eq(D(5,2)),
                            symbol2.eq(D(5,2))
                        ]
        return m