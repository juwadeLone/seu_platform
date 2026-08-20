# Export placed primitives from the current design (open checkpoint or live impl).
# Fields follow 布局感知_ECC_仿真平台搭建指南.md section 7.2 (stage tags filled later).

proc _csv_escape {s} {
  set s [string map {"\"" "\"\""} $s]
  if {[string match {*,*} $s] || [string match {*"*} $s]} {
    return "\"$s\""
  }
  return $s
}

proc export_primitive_map {csv_path} {
  set fp [open $csv_path w]
  puts $fp "unit_id,hier_cell,ref_name,loc,bel,site,tile,grid_x,grid_y,stage_id,module_role,data_role,ecc_codeword_rule,ecc_symbol_rule,is_used,is_shared"
  set i 0
  set placed 0
  foreach c [get_cells -hierarchical -quiet -filter {IS_PRIMITIVE == 1}] {
    set name [get_property NAME $c]
    set ref  [get_property REF_NAME $c]
    set loc  [get_property LOC $c]
    set bel  [get_property BEL $c]
    set site ""
    set tile ""
    set gx ""
    set gy ""
    if {$loc ne ""} {
      incr placed
      set sites [get_sites -quiet -of_objects $c]
      if {[llength $sites]} {
        set site [lindex $sites 0]
        set tiles [get_tiles -quiet -of_objects $site]
        if {[llength $tiles]} { set tile [lindex $tiles 0] }
        set gx [get_property RPM_X $site]
        set gy [get_property RPM_Y $site]
      }
      if {$gx eq "" || $gy eq ""} {
        if {[regexp {X([0-9]+)Y([0-9]+)} $loc -> x y]} {
          set gx $x
          set gy $y
        }
      }
    }
    set used [expr {$loc ne "" ? 1 : 0}]
    puts $fp [join [list \
      $i \
      [_csv_escape $name] \
      [_csv_escape $ref] \
      [_csv_escape $loc] \
      [_csv_escape $bel] \
      [_csv_escape $site] \
      [_csv_escape $tile] \
      $gx $gy \
      {} {} {} {} {} \
      $used 0 \
    ] ,]
    incr i
    if {($i % 20000) == 0} { puts "INFO: exported $i cells..." }
  }
  close $fp
  puts "INFO: primitive_map $csv_path  cells=$i placed=$placed"
}

proc export_from_dcp {dcp csv_path} {
  open_checkpoint $dcp
  export_primitive_map $csv_path
}
