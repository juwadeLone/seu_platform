# OOC synth+place+route for P1, then write DCP + primitive_map.csv.
# Tool: Vivado 2018.3 (this Windows machine). Linux paper flow used 2022.1;
# numbers here are layout-export provenance, not mixed into Yosys paper tables.
#
# Usage:
#   vivado -mode batch -source run_p1_ooc_dcp.tcl

set rtl_dir  {F:/fft1024_ft_exp/vivado/K_P1_pfft/hdl/rtl}
set xdc_file {F:/fft1024_ft_exp/vivado/constraints/kernel_clk_125mhz.xdc}
set part     xc7vx690tffg1761-2
set top      top_p1_pfft_ecc
set outdir   {C:/Users/zhuao/tcas/code/layout_ecc_sim/data/layout/p1_ooc_win}

file mkdir $outdir
set_param general.maxThreads 8

puts "INFO: RTL $rtl_dir"
puts "INFO: OUT $outdir"

create_project -in_memory -part $part
set_property target_language Verilog [current_project]

set svs [glob -nocomplain [file join $rtl_dir *.sv] [file join $rtl_dir *.v]]
if {![llength $svs]} { error "no RTL in $rtl_dir" }
add_files -norecurse $svs
set_property top $top [current_fileset]
update_compile_order -fileset sources_1
read_xdc $xdc_file

puts "INFO: synth_design OOC $top"
synth_design -mode out_of_context -top $top -part $part -max_bram 0
puts "INFO: opt/place/route"
opt_design
place_design
phys_opt_design
route_design
phys_opt_design

set dcp [file join $outdir P1_routed_ooc.dcp]
write_checkpoint -force $dcp
report_timing_summary -file [file join $outdir timing_summary.rpt]
report_utilization -file [file join $outdir util.rpt]
report_utilization -hierarchical -file [file join $outdir util_hier.rpt]
catch { report_power -file [file join $outdir power.rpt] }

# --- primitive map (guide 7.2) ---------------------------------------------
source [file join [file dirname [info script]] export_layout.tcl]
export_primitive_map [file join $outdir primitive_map.csv]

puts "INFO: DCP $dcp"
puts "INFO: done"
close_project
