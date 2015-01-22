import time
import numpy as np

from VISolver.Domains.BloodBank import BloodBank, CreateRandomNetwork

# from VISolver.Solvers.Euler import Euler
# from VISolver.Solvers.Extragradient import EG
# from VISolver.Solvers.AcceleratedGradient import AG
# from VISolver.Solvers.HeunEuler import HeunEuler
# from VISolver.Solvers.AdamsBashforthEuler import ABEuler
from VISolver.Solvers.CashKarp import CashKarp

from VISolver.Projection import RPlusProjection
from VISolver.Solver import Solve
from VISolver.Options import (
    DescentOptions, Miscellaneous, Reporting, Termination, Initialization)
from VISolver.Log import PrintSimResults, PrintSimStats


def Demo():

    #__BLOOD_BANK__##################################################

    # Define Network and Domain
    Network = CreateRandomNetwork(nC=2,nB=2,nD=2,nR=2,seed=0)
    Domain = BloodBank(Network=Network,alpha=2)

    # Set Method
    # Method = Euler(Domain=Domain,P=RPlusProjection())
    # Method = EG(Domain=Domain,P=RPlusProjection())
    # Method = AG(Domain=Domain,P=RPlusProjection())
    # Method = HeunEuler(Domain=Domain,P=RPlusProjection(),Delta0=1e-5)
    # Method = ABEuler(Domain=Domain,P=RPlusProjection(),Delta0=1e-5)
    Method = CashKarp(Domain=Domain,P=RPlusProjection(),Delta0=1e-6)

    # Initialize Starting Point
    Start = np.zeros(Domain.Dim)

    # Calculate Initial Gap
    gap_0 = Domain.gap_rplus(Start)

    # Set Options
    Init = Initialization(Step=-1e-10)
    # Init = Initialization(Step=-0.1)
    Term = Termination(MaxIter=25000,Tols=[(Domain.gap_rplus,1e-6*gap_0)])
    Repo = Reporting(Requests=[Domain.gap_rplus, 'Step', 'F Evaluations',
                               'Projections'])
    Misc = Miscellaneous()
    Options = DescentOptions(Init,Term,Repo,Misc)

    # Print Stats
    PrintSimStats(Domain,Method,Options)

    # Start Solver
    tic = time.time()
    BloodBank_Results = Solve(Start,Method,Domain,Options)
    toc = time.time() - tic

    # Print Results
    PrintSimResults(Options,BloodBank_Results,Method,toc)

if __name__ == '__main__':
    Demo()