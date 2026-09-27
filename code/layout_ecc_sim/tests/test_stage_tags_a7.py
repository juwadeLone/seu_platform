"""A7 hier_cell tag parser tests (iterative 256 FFT, not P1 sN)."""
import unittest

from layout_ecc.stage_tags_a7 import bucket_of, majority_site, tag


class TestA7Tags(unittest.TestCase):
    def test_cmd_seq_is_control(self):
        self.assertEqual(tag("u_cmd_seq/state_reg[2]")[1], "control")
        self.assertEqual(tag("A7_fpga_top/u_cmd_seq")[1], "control")

    def test_uart_is_control(self):
        self.assertEqual(tag("u_uart_cmd_if/hdr")[1], "control")
        self.assertEqual(tag("uart_rx/shift")[1], "control")

    def test_cs_builder(self):
        st, role, _ = tag("u_cs_builder/u_alu/u_mul")
        self.assertEqual(role, "coeff_build")
        self.assertEqual(st, 0)

    def test_fft_lanes(self):
        for i in range(4):
            st, role, _ = tag(f"u_fft2d/u_row/u_fft{i}/ram_reg")
            self.assertEqual((st, role), (i + 1, "fft_core"))

    def test_phase_gens(self):
        self.assertEqual(tag("u_fft2d/u_row/u_gen_hcs/p")[0:2], (5, "phase_gen"))
        self.assertEqual(tag("u_fft2d/u_row/u_gen_hr/p")[0:2], (6, "phase_gen"))
        self.assertEqual(tag("u_fft2d/u_row/u_gen_ha/p")[0:2], (7, "phase_gen"))

    def test_fft_axi_is_ddr(self):
        self.assertEqual(tag("u_fft2d/u_row/u_rd/aw")[1], "ddr_if")
        self.assertEqual(tag("u_fft2d/u_row/u_wr/w")[1], "ddr_if")

    def test_fft_board_ctrl(self):
        self.assertEqual(tag("u_fft2d/state_reg")[1], "fft_ctrl")

    def test_mig_and_swap(self):
        self.assertEqual(tag("u_block_design_top/u_mig_7series_0/u")[1], "ddr_if")
        self.assertEqual(tag("u_swap/u_reader")[1], "transpose")

    def test_comms_and_clock(self):
        self.assertEqual(tag("udp_eth_rx/crc")[1], "comms")
        self.assertEqual(tag("u_telem_engine/w")[1], "comms")
        self.assertEqual(tag("inst1_clk_and_rst/mmcm")[1], "clock")

    def test_sem_is_test_infra(self):
        st, role, _ = tag("sem_0/controller")
        self.assertEqual((st, role), (-1, "test_infra"))

    def test_unknown(self):
        self.assertEqual(tag("mystery_cell/x")[1], "unknown")
        self.assertEqual(tag("")[1], "unknown")

    def test_buckets(self):
        self.assertEqual(bucket_of("control"), "control")
        self.assertEqual(bucket_of("fft_core"), "fft_datapath")
        self.assertEqual(bucket_of("coeff_build"), "fft_datapath")
        self.assertEqual(bucket_of("ddr_if"), "bram_dsp_col")
        self.assertEqual(bucket_of("test_infra"), "test_infra")
        self.assertEqual(bucket_of("comms"), "other")

    def test_majority_shared_lanes(self):
        maj = majority_site([
            "u_fft2d/u_row/u_fft0/a",
            "u_fft2d/u_row/u_fft0/b",
            "u_fft2d/u_row/u_fft1/c",
        ])
        self.assertTrue(maj["is_shared"])
        self.assertEqual(maj["module_role"], "fft_core")
        self.assertEqual(maj["stages"], [1, 2])


if __name__ == "__main__":
    unittest.main()
