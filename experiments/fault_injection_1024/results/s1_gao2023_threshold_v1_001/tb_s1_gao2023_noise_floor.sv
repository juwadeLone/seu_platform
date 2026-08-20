`timescale 1ns/1ps
// Fault-free Gao [7,4,3] syndrome dump for Gao 2023 3-sigma on K_S1.
module tb_s1_gao2023_noise_floor;
  localparam integer INPUT_BEATS = 2560;
  localparam integer EXPECTED_BEATS = 2048;
  localparam integer TIMEOUT_CYCLES = 20000;

  reg clk = 0, rst = 1, in_valid = 0, in_last = 0;
  reg signed [34:0] in0_re, in0_im, in1_re, in1_im, in2_re, in2_im, in3_re, in3_im;
  wire out_valid, out_last;
  wire signed [34:0] out0_re, out0_im, out1_re, out1_im, out2_re, out2_im, out3_re, out3_im;
  reg [279:0] input_mem[0:INPUT_BEATS-1], expected_mem[0:EXPECTED_BEATS-1];
  wire [279:0] packed_output = {out0_re, out0_im, out1_re, out1_im, out2_re, out2_im, out3_re, out3_im};

  integer input_index = 0, output_index = 0, cycle_count = 0, errors = 0;
  integer csv;
  string csv_path, input_hex, expected_hex;

  top_s1_gao_subfft_ecc dut(
    clk, rst, in_valid, in_last,
    in0_re, in0_im, in1_re, in1_im, in2_re, in2_im, in3_re, in3_im,
    out_valid, out_last,
    out0_re, out0_im, out1_re, out1_im, out2_re, out2_im, out3_re, out3_im
  );

  always #5 clk = ~clk;

  initial begin
    if (!$value$plusargs("CSV=%s", csv_path)) csv_path = "syndrome_faultfree.csv";
    if (!$value$plusargs("INPUT_HEX=%s", input_hex))
      input_hex = "/home/xdu/JuWade_research/fft1024_ft_exp/kernels/S1/vectors/qualification_input_10frames.hex";
    if (!$value$plusargs("EXPECTED_HEX=%s", expected_hex))
      expected_hex = "/home/xdu/JuWade_research/fft1024_ft_exp/kernels/S1/vectors/qualification_subfft_expected_8frames.hex";
    $readmemh(input_hex, input_mem);
    $readmemh(expected_hex, expected_mem);
    csv = $fopen(csv_path, "w");
    if (csv == 0) begin
      $display("FAIL open CSV %s", csv_path);
      $finish;
    end
    $fwrite(csv, "cycle,stage,syn0r,syn0i,syn1r,syn1i,syn2r,syn2i,found\n");
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
    if (dut.pv_d3) begin
      $fwrite(csv, "%0d,8,%0d,%0d,%0d,%0d,%0d,%0d,%0d\n",
              cycle_count, dut.syn0r, dut.syn0i, dut.syn1r, dut.syn1i, dut.syn2r, dut.syn2i, dut.found);
    end
    if (out_valid) begin
      if (output_index < EXPECTED_BEATS) begin
        if (packed_output !== expected_mem[output_index]) begin
          errors = errors + 1;
          if (errors <= 5) $display("S1 MISMATCH beat=%0d", output_index);
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
