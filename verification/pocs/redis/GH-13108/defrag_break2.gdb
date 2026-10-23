set pagination off
set breakpoint pending on
break activeDefragCycle
commands
silent
printf "DEFRAG_HIT caller="
frame 1
continue
end
run
