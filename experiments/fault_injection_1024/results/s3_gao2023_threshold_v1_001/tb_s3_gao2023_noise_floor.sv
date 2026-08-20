`timescale 1ns/1ps
// Fault-free raw-syndrome dump for Gao 2023 3-sigma calibration on K_S3.
module tb_s3_gao2023_noise_floor;
  localparam integer INPUT_BEATS = 2560;
  localparam integer EXPECTED_BEATS = 2048;
  localparam integer TIMEOUT_CYCLES = 12000;

  reg clk = 0, rst = 1, in_valid = 0, in_last = 0;
  reg signed [34:0] in0_re, in0_im, in1_re, in1_im, in2_re, in2_im, in3_re, in3_im;
  wire out_valid, out_last;
  wire signed [34:0] out0_re, out0_im, out1_re, out1_im, out2_re, out2_im, out3_re, out3_im;
  reg [279:0] input_mem[0:INPUT_BEATS-1], expected_mem[0:EXPECTED_BEATS-1];
  wire [279:0] packed_output = {out0_re, out0_im, out1_re, out1_im, out2_re, out2_im, out3_re, out3_im};

  integer input_index = 0, output_index = 0, cycle_count = 0, errors = 0;
  integer csv;
  string csv_path, input_hex, expected_hex;

  top_s3_subfft_ecc dut(
    clk, rst, in_valid, in_last,
    in0_re, in0_im, in1_re, in1_im, in2_re, in2_im, in3_re, in3_im,
    out_valid, out_last,
    out0_re, out0_im, out1_re, out1_im, out2_re, out2_im, out3_re, out3_im
  );

  always #5 clk = ~clk;

  task dump_stage;
    input integer st;
    input syn_v;
    input signed [38:0] sy0r, sy0i, sy1r, sy1i;
    input found;
    begin
      if (syn_v) begin
        $fwrite(csv, "%0d,%0d,%0d,%0d,%0d,%0d,%0d\n",
                cycle_count, st, sy0r, sy0i, sy1r, sy1i, found);
      end
    end
  endtask

  initial begin
    if (!$value$plusargs("CSV=%s", csv_path)) csv_path = "syndrome_faultfree.csv";
    if (!$value$plusargs("INPUT_HEX=%s", input_hex))
      input_hex = "/home/xdu/JuWade_research/fft1024_ft_exp/kernels/S3/vectors/qualification_input_10frames.hex";
    if (!$value$plusargs("EXPECTED_HEX=%s", expected_hex))
      expected_hex = "/home/xdu/JuWade_research/fft1024_ft_exp/kernels/S3/vectors/qualification_subfft_expected_8frames.hex";
    $readmemh(input_hex, input_mem);
    $readmemh(expected_hex, expected_mem);
    csv = $fopen(csv_path, "w");
    if (csv == 0) begin
      $display("FAIL open CSV %s", csv_path);
      $finish;
    end
    $fwrite(csv, "cycle,stage,sy0r,sy0i,sy1r,sy1i,found\n");
    repeat (4) @(posedge clk);
    @(negedge clk);
    rst = 0;
    for (input_index = 0; input_index < INPUT_BEATS; input_index = input_index + 1) begin
      in_valid = 1;
      in_last = ((input_index % 256) == 255);
      {in0_re, in0_im, in1_re, in1_im, in2_re, in2_im, in3_re, in3_im} = input_mem[input_index];
      @(negedge clk);
    end
    in_valid = 0;
    in_last = 0;
  end

  always @(negedge clk) if (!rst) begin
    cycle_count = cycle_count + 1;
    dump_stage(1, dut.u.s1.syn_v, dut.u.s1.sy0r, dut.u.s1.sy0i, dut.u.s1.sy1r, dut.u.s1.sy1i, dut.u.s1.u_apply.found);
    dump_stage(2, dut.u.s2.syn_v, dut.u.s2.sy0r, dut.u.s2.sy0i, dut.u.s2.sy1r, dut.u.s2.sy1i, dut.u.s2.u_apply.found);
    dump_stage(3, dut.u.s3.syn_v, dut.u.s3.sy0r, dut.u.s3.sy0i, dut.u.s3.sy1r, dut.u.s3.sy1i, dut.u.s3.u_apply.found);
    dump_stage(4, dut.u.s4.syn_v, dut.u.s4.sy0r, dut.u.s4.sy0i, dut.u.s4.sy1r, dut.u.s4.sy1i, dut.u.s4.u_apply.found);
    dump_stage(5, dut.u.s5.syn_v, dut.u.s5.sy0r, dut.u.s5.sy0i, dut.u.s5.sy1r, dut.u.s5.sy1i, dut.u.s5.u_apply.found);
    dump_stage(6, dut.u.s6.syn_v, dut.u.s6.sy0r, dut.u.s6.sy0i, dut.u.s6.sy1r, dut.u.s6.sy1i, dut.u.s6.u_apply.found);
    dump_stage(7, dut.u.s7.syn_v, dut.u.s7.sy0r, dut.u.s7.sy0i, dut.u.s7.sy1r, dut.u.s7.sy1i, dut.u.s7.u_apply.found);
    dump_stage(8, dut.u.s8.syn_v, dut.u.s8.sy0r, dut.u.s8.sy0i, dut.u.s8.sy1r, dut.u.s8.sy1i, dut.u.s8.u_apply.found);
    if (out_valid) begin
      if (output_index < EXPECTED_BEATS) begin
        if (packed_output !== expected_mem[output_index]) begin
          errors = errors + 1;
          if (errors <= 5) $display("S3 MISMATCH beat=%0d", output_index);
        end
        output_index = output_index + 1;
        if (output_index == EXPECTED_BEATS) begin
          $display("SUMMARY beats=%0d errors=%0d cycles=%0d", output_index, errors, cycle_count);
          $fclose(csv);
          if (errors == 0) $display("PASS bitexact");
          else $display("FAIL bitexact");
          $finish;
        end
      end
    end
    if (cycle_count > TIMEOUT_CYCLES) begin
      $display("TIMEOUT beats=%0d errors=%0d", output_index, errors);
      $fclose(csv);
      $finish;
    end
  end
endmodule
