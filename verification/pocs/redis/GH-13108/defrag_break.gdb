set pagination off
set breakpoint pending on
break activeDefragCycle
commands
silent
printf "DEFRAG_HIT\n"
continue
end
run
