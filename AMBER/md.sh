PRMTOP=system.prmtop
INPCRD=system.inpcrd

pmemd.cuda -O -i min1.in -o min1.out -p $PRMTOP -c $INPCRD -r min1.rst -ref $INPCRD
pmemd.cuda -O -i min2.in -o min2.out -p $PRMTOP -c min1.rst -r min2.rst
pmemd.cuda -O -i heat.in -o heat.out -p $PRMTOP -c min2.rst -r heat.rst -x heat.mdcrd -ref min2.rst -e heat.mden
pmemd.cuda -O -i pressure.in -o pressure.out -p $PRMTOP -c heat.rst -r pres.rst -x pres.mdcrd -ref heat.rst -e pres.mden
pmemd.cuda -O -i equil.in -o equil.out -p $PRMTOP -c pres.rst -r equil.rst -x equil.mdcrd -ref pres.rst -e equil.mden
pmemd.cuda -O -i md.in -o md_1.out -p $PRMTOP -c equil.rst -r md_1.rst -x md_1.nc -ref equil.rst -e md_1.mden
