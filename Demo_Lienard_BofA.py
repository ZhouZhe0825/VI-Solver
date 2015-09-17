# import time
import numpy as np

from VISolver.Domains.Lienard import Lienard

from VISolver.Solvers.HeunEuler_LEGS import HeunEuler_LEGS

from VISolver.Solver import Solve
from VISolver.Options import (
    DescentOptions, Miscellaneous, Reporting, Termination, Initialization)
from VISolver.Log import PrintSimStats

from VISolver.Utilities import ListONP2NP
from VISolver.BoA.Utilities import aug_grid
from VISolver.BoA.MCGrid_Enhanced import MCT

from matplotlib.colors import colorConverter
from matplotlib import pyplot as plt
import matplotlib as mpl

from VISolver.BoA.Plotting import plotBoA

from IPython import embed

# from sklearn.svm import SVC


def Demo():

    #__LIENARD_SYSTEM__##################################################

    # Define Network and Domain
    Domain = Lienard()

    # Set Method
    Method = HeunEuler_LEGS(Domain=Domain,Delta0=1e-5)

    # Set Options
    Init = Initialization(Step=1e-5)
    Term = Termination(MaxIter=5e4)
    Repo = Reporting(Requests=['Data','Step'])
    Misc = Miscellaneous()
    Options = DescentOptions(Init,Term,Repo,Misc)
    args = (Method,Domain,Options)
    sim = Solve

    # Print Stats
    PrintSimStats(Domain,Method,Options)

    grid = [np.array([-2.5,2.5,13])]*2
    grid = ListONP2NP(grid)
    grid = aug_grid(grid)
    Dinv = np.diag(1./grid[:,3])
    r = 1.1*max(grid[:,3])

    results = MCT(sim,args,grid,nodes=8,parallel=True,limit=5,AVG=0.,
                  eta_1=1.2,eta_2=.95,eps=1.,
                  L=8,q=2,r=r,Dinv=Dinv)
    ref, data, p, i, avg, bndry_ids, starts = results

    plotBoA(ref,data,grid,color=True,scatter=True)

    # plt.figure()
    # c = plt.cm.hsv(np.random.rand(len(ref)))
    # white = colorConverter.to_rgba('white')
    # for cat,lam in enumerate(ref):

    #     samples = data[hash(str(lam))]
    #     if samples != []:
    #         n = len(samples)
    #         X = np.empty((len(samples)*2,2))
    #         for idx,sample in enumerate(samples):
    #             X[idx] = sample[0]
    #             X[idx+len(samples)] = sample[1]
    #         Y = np.zeros(len(samples)*2)
    #         Y[:n] = 1

    #         clf = SVC()
    #         clf.fit(X,Y)

    #         xx, yy = np.meshgrid(np.linspace(grid[0,0],grid[0,1],500),
    #                              np.linspace(grid[1,0],grid[1,1],500))
    #         Z = clf.decision_function(np.c_[xx.ravel(),yy.ravel()])
    #         Z = Z.reshape(xx.shape)
    #         Zma = np.ma.masked_where(Z < 0,Z)

    #         cmap = mpl.colors.LinearSegmentedColormap.from_list('my_cmap',
    #                                                             [white,c[cat]],
    #                                                             256)
    #         cmap.set_bad(color='w',alpha=0.0)

    #         plt.imshow(Zma, interpolation='nearest',
    #                    extent=(xx.min(), xx.max(), yy.min(), yy.max()),
    #                    aspect='auto', origin='lower', cmap=cmap, zorder=0)
    #         plt.contour(xx, yy, Z, colors='k', levels=[0], linewidths=2,
    #                     linetypes='-.', zorder=1)
    #         plt.scatter(X[:n, 0], X[:n, 1], s=30, c=c[cat], zorder=2)

    # ax = plt.gca()
    # ax.set_xlim([-2.5,2.5])
    # ax.set_ylim([-2.5,2.5])
    # ax.set_aspect('equal')
    # plt.savefig('bndry_pts.png',format='png')

    plt.figure()
    pmap = np.swapaxes(np.reshape(p,tuple(grid[:,2])),0,1)
    plt.imshow(pmap,'jet',origin='lower')
    plt.gca().set_aspect('equal')

    plt.show()

    embed()

if __name__ == '__main__':
    Demo()
