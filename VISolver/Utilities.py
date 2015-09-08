from __future__ import division
import numpy as np
import random
import itertools
# https://github.com/uqfoundation/pathos
import pathos.multiprocessing as mp
import time
from IPython import embed


#Utilities
def MachineLimit_Exp(Var, Const, L=-700., H=700.):
    Var_mn = np.abs(Var)
    Var_mx = np.abs(Var)
    Const_mn = np.min(np.sign(Var)*Const)
    Const_mx = np.max(np.sign(Var)*Const)
    if np.abs(Var)*Const_mn < L:
        Var_mn = np.abs(L/Const_mn)
    if np.abs(Var)*Const_mx > H:
        Var_mx = np.abs(H/Const_mx)
    return np.min([Var_mn,Var_mx,np.abs(Var)])*np.sign(Var)


def GramSchmidt(A,normalize=True):
    U = A.copy()
    for i in xrange(A.shape[0]):
        vi = A[:,i]
        proj = 0*vi
        for j in xrange(i):
            uj = U[:,j]
            proj += np.dot(vi,uj)/np.dot(uj,uj)*uj
        U[:,i] = vi - proj

    if normalize:
        return U/np.linalg.norm(U,axis=0)
    return U


def ListONP2NP(L):
    arr = np.empty((len(L),)+L[0].shape)
    for idx,x in enumerate(L):
        arr[idx] = x
    return arr


# Following functions added for grid sampling
def aug_grid(grid,op=1):
    if op == 1:
        inc = (grid[:,1]-grid[:,0])/(grid[:,2]-1)
        return np.hstack((grid,inc[:,None]))
    else:
        N = (grid[:,1]-grid[:,0])/grid[:,2] + 1
        return np.hstack((grid[:,:2],N[:,None],grid[:,2]))


# shape is tuple containing number of points along each dimension of the grid
def int2ind(i,shape):
    assert i >= 0
    assert i < np.prod(shape)
    ind = ()
    divisors = np.cumprod(shape[:0:-1])[::-1]
    for d in divisors:
        q,i = divmod(i,d)
        ind += (q,)
    ind += (i,)
    return ind


# grid is column array of start, end, N, inc
def ind2pt(ind,grid):
    assert len(ind) == grid.shape[0]
    assert all(i < grid[j,2] for j,i in enumerate(ind))
    assert all(i >= 0 for i in ind)
    return grid[:,0] + np.multiply(ind,grid[:,3])


# grid is column array of start, end, N, inc
def ind2pt2(ind,grid):
    assert len(ind) == grid.shape[0]
    return grid[:,0] + np.multiply(ind,grid[:,3])


def ind2int(ind,shape):
    assert len(ind) == len(shape)
    assert all(x < y for x,y in zip(ind,shape))
    assert all(x >= 0 for x in ind)
    sizes = np.cumprod(shape[:0:-1])[::-1]
    return int(np.dot(ind[:-1],sizes)+ind[-1])


def pt2inds(pt,grid):
    lo = np.array([int(i) for i in (pt-grid[:,0])//grid[:,3]])
    rng = 2*np.ones(len(lo))
    bnds = []
    for idx in np.ndindex(*rng):
        vert = tuple(np.add(idx,lo))
        if all(i >= 0 and i < grid[j,2] for j,i in enumerate(vert)):
            bnds.append(vert)
    return bnds


def pt2inds2(pt,grid):
    lo = np.array([int(i) for i in (pt-grid[:,0])//grid[:,3]])
    rng = 2*np.ones(len(lo))
    # bnds = []
    # for idx in np.ndindex(*rng):
    #     vert = tuple(np.add(idx,lo))
    #     if all(i >= 0 and i < grid[j,2] for j,i in enumerate(vert)):
    #         bnds.append(vert)
    return [tuple(np.add(idx,lo)) for idx in np.ndindex(*rng)]


def neighbors(ind,grid,r,q=None,Dinv=1):
    lo = grid[:,0]
    hi = grid[:,1]
    inc = grid[:,3]
    i_max = np.array([int(v) for v in r//inc])
    neigh = []
    cube = np.ndindex(*(i_max*2+1))
    for idx in cube:
        offset = [v - i_max[k] for k,v in enumerate(idx)]
        if any(v != 0 for k,v in enumerate(offset)):  # not origin
            n = np.add(offset,ind)
            loc = lo+n*inc
            if all(loc >= lo) and all(loc <= hi) and \
               np.linalg.norm(np.dot(offset*inc,Dinv)) < r:
                neigh += [tuple(n)]
    if q is None:
        return neigh
    selected = random.sample(neigh,min(q,len(neigh)))
    return selected, neigh


def update_LamRef(ref,lams,eps,data,ref_ept,endpts):
    if ref is None:
        ref = lams[0].copy()[None]
        ref_ept = endpts[0].copy()[None]
        data[hash(str(lams[0]))] = []
    for l,lam in enumerate(lams):
        # same0 = [np.allclose(lam,_ref,rtol=.2,atol=1.) for _ref in ref]
        ept = endpts[l]
        same_ept = [np.allclose(ept,_ref,rtol=.1,atol=1.) for _ref in ref_ept]
        same = []
        # print(len(same_ept))
        # print(len(ref))
        for e,is_same_ept in enumerate(same_ept):
            if is_same_ept:
                same += [np.allclose(lam,ref[e],rtol=.4,atol=1.)]
            else:
                same += [np.allclose(lam,ref[e],rtol=.2,atol=1.)]
        # print(same)
        # print(same0)
        if not any(same):
            ref = np.concatenate((ref,[lam]))
            ref_ept = np.concatenate((ref_ept,[ept]))
            data[hash(str(lam))] = []
    return ref, data, ref_ept


def adjustLams2Ref(ref,lams):
    for idx,lam in enumerate(lams):
        diff = ref - lam
        lams[idx] = ref[np.argmin(np.linalg.norm(diff,axis=1))]


# ids should be list of ints representing sampled points with center at index 0
def update_Prob_Data(ids,shape,grid,lams,eps,p,eta_1,eta_2,data):
    toZero = set()
    boundry_pairs = 0
    for pair in itertools.combinations(np.arange(len(lams)),2):
        lam_a = lams[pair[0]]
        lam_b = lams[pair[1]]
        same = all(lam_a == lam_b)
        if not same:
            boundry_pairs += 1
            id_a = ids[pair[0]]
            id_b = ids[pair[1]]
            toZero.update([id_a,id_b])
            p[ids[1:]] *= eta_1
            # add pair to corresponding dataset
            pt_a = ind2pt(int2ind(id_a,shape),grid)
            pt_b = ind2pt(int2ind(id_b,shape),grid)
            data[hash(str(lam_a))] += [[pt_a,pt_b]]
            data[hash(str(lam_b))] += [[pt_b,pt_a]]
        else:
            p[ids[pair[0]]] *= eta_2
            p[ids[pair[1]]] *= eta_2
    for z in toZero:
        p[z] = 0
    return p, data, boundry_pairs, toZero


# def MCLE_BofA_ID(sim,args,grid,limit=1,AVG=.01,eta_1=1.2,eta_2=.95,
#                  eps=1.,L=1,q=2,r=1.1,Dinv=1):
#     shape = tuple(grid[:,2])
#     p = np.ones(np.prod(shape))/np.prod(shape)
#     ids = range(int(np.prod(shape)))

#     ref = None
#     data = {}
#     B_pairs = 0

#     i = 0
#     avg = np.inf
#     bndry_ids_master = set()
#     starts = set()
#     while (i <= limit) or (avg > AVG):
#         print(i)
#         center_ids = np.random.choice(ids,size=L,p=p)
#         starts |= set(center_ids)
#         center_inds = [int2ind(center_id,shape) for center_id in center_ids]
#         groups = []
#         for center_ind in center_inds:
#             selected, neigh = neighbors(center_ind,grid,r,q,Dinv)
#             group_inds = [center_ind] + selected
#             group_ids = [ind2int(ind,shape) for ind in group_inds]
#             group_pts = [ind2pt(ind,grid) for ind in group_inds]
#             print(group_pts)
#             lams = []
#             for start in group_pts:
#                 results = sim(start,*args)
#                 lams += [results.TempStorage['Lyapunov'][-1]]
#             ref, data = update_LamRef(ref,lams,eps,data)
#             groups += [[group_ids,lams]]
#         for group in groups:
#             lams = group[1]
#             adjustLams2Ref(ref,lams)
#         bndry_ids_all = set()
#         for group in groups:
#             group_ids, group_lams = group
#             p, data, b_pairs, bndry_ids = update_Prob_Data(group_ids,shape,grid,
#                                                            group_lams,eps,
#                                                            p,eta_1,eta_2,
#                                                            data)
#             B_pairs += b_pairs
#             bndry_ids_all |= bndry_ids
#         p = p/np.sum(p)
#         i += 1
#         avg = B_pairs/((q+1)*L*i)
#         bndry_ids_master |= bndry_ids_all
#     return ref, data, p, i, avg, bndry_ids_master, starts


# def compLEs(x):
#     center_ind,sim,args,grid,shape,eps,q,r,Dinv = x
#     selected, neigh = neighbors(center_ind,grid,r,q,Dinv)
#     group_inds = [center_ind] + selected
#     group_ids = [ind2int(ind,shape) for ind in group_inds]
#     group_pts = [ind2pt(ind,grid) for ind in group_inds]
#     lams = []
#     for start in group_pts:
#         results = sim(start,*args)
#         lams += [results.TempStorage['Lyapunov'][-1]]
#     return [group_ids,lams]


# def MCLE_BofA_ID_par(sim,args,grid,nodes=8,limit=1,AVG=.01,eta_1=1.2,eta_2=.95,
#                      eps=1.,L=1,q=2,r=1.1,Dinv=1):
#     shape = tuple(grid[:,2])
#     p = np.ones(np.prod(shape))/np.prod(shape)
#     ids = range(int(np.prod(shape)))

#     ref = None
#     data = {}
#     B_pairs = 0

#     pool = mp.ProcessingPool(nodes=nodes)

#     i = 0
#     avg = np.inf
#     bndry_ids_master = set()
#     starts = set()
#     while (i < limit) or (avg > AVG):
#         print(i)
#         center_ids = np.random.choice(ids,size=L,p=p)
#         starts |= set(center_ids)
#         center_inds = [int2ind(center_id,shape) for center_id in center_ids]
#         x = [(ind,sim,args,grid,shape,eps,q,r,Dinv) for ind in center_inds]
#         groups = pool.map(compLEs,x)
#         for group in groups:
#             lams = group[1]
#             ref, data = update_LamRef(ref,lams,eps,data)
#         for group in groups:
#             lams = group[1]
#             adjustLams2Ref(ref,lams)
#         bndry_ids_all = set()
#         for group in groups:
#             group_ids, group_lams = group
#             p, data, b_pairs, bndry_ids = update_Prob_Data(group_ids,shape,grid,
#                                                            group_lams,eps,
#                                                            p,eta_1,eta_2,
#                                                            data)
#             B_pairs += b_pairs
#             bndry_ids_all |= bndry_ids
#         p = p/np.sum(p)
#         i += 1
#         avg = B_pairs/((q+1)*L*i)
#         bndry_ids_master |= bndry_ids_all
#     return ref, data, p, i, avg, bndry_ids_master, starts


def compLEs_wTraj(x):
    center_ind,sim,args,grid,shape,eps,q,r,Dinv = x
    selected, neigh = neighbors(center_ind,grid,r,q,Dinv)
    group_inds = [center_ind] + selected
    group_ids = [ind2int(ind,shape) for ind in group_inds]
    group_pts = [ind2pt(ind,grid) for ind in group_inds]
    ddiag = np.linalg.norm(grid[:,3])
    # dmax = np.linalg.norm(grid[:,3])*.5
    print(group_pts[0])
    endpts = []
    lams = []
    bnd_ind_sum = {}
    for start in group_pts:
        results = sim(start,*args)
        endpt = results.TempStorage['Data'][-1]
        endpts += [endpt]
        lam = results.TempStorage['Lyapunov'][-1]
        lams += [lam]
        c = np.max(np.abs(lam))
        t = np.cumsum([0]+results.PermStorage['Step'][:-1])
        T = t[-1]
        pt0 = results.PermStorage['Data'][0]
        cube_inds = pt2inds2(pt0,grid)
        cube_pts = np.array([ind2pt2(ind,grid) for ind in cube_inds])
        for i, pt in enumerate(results.PermStorage['Data']):
            ti = t[i]
            dt = results.PermStorage['Step'][i]
            ds = np.linalg.norm(pt-cube_pts,axis=1)
            if any(ds > ddiag):
                cube_inds = pt2inds2(pt,grid)
                cube_pts = np.array([ind2pt2(ind,grid) for ind in cube_inds])
                ds = np.linalg.norm(pt-cube_pts,axis=1)
            inbnds = np.all(np.logical_and(cube_pts >= grid[:,0],
                                           cube_pts <= grid[:,1]),
                            axis=1)
            for idx, cube_ind in enumerate(cube_inds):
                if inbnds[idx]:
                    # d = ds[idx]
                    # d_fac = max(1-d/dmax,0)
                    d_fac = 1
                    if not (cube_ind in bnd_ind_sum):
                        bnd_ind_sum[cube_ind] = [0,0]
                    bnd_ind_sum[cube_ind][0] += np.exp(-c*ti/T*d_fac)*dt
                    bnd_ind_sum[cube_ind][1] += dt
    return [group_ids,lams,bnd_ind_sum,endpts]
    # return [group_ids,lams,bnd_ind_sum]


def MCLET_BofA_ID_par(sim,args,grid,nodes=8,limit=1,AVG=.01,eta_1=1.2,eta_2=.95,
                      eps=1.,L=1,q=2,r=1.1,Dinv=1):
    shape = tuple(grid[:,2])
    p = np.ones(np.prod(shape))/np.prod(shape)
    ids = range(int(np.prod(shape)))

    ref = None
    ref_ept = None
    data = {}
    B_pairs = 0

    pool = mp.ProcessingPool(nodes=nodes)

    i = 0
    avg = np.inf
    bndry_ids_master = set()
    starts = set()
    while (i < limit) and (avg > AVG):
        print(i)
        center_ids = np.random.choice(ids,size=L,p=p)
        starts |= set(center_ids)
        center_inds = [int2ind(center_id,shape) for center_id in center_ids]
        x = [(ind,sim,args,grid,shape,eps,q,r,Dinv) for ind in center_inds]
        groups = pool.map(compLEs_wTraj,x)
        bnd_ind_sum_master = {}
        for group in groups:
            bnd_ind_sum = group[2]
            for key,val in bnd_ind_sum.iteritems():
                if not (key in bnd_ind_sum_master):
                    parent = group[0][0]  # get rid of parent stuff
                    bnd_ind_sum_master[key] = [0,0,parent]  # not right
                bnd_ind_sum_master[key][0] += val[0]
                bnd_ind_sum_master[key][1] += val[1]
        for group in groups:
            lams = group[1]
            endpts = group[3]
            # add endpts as input to update_LamRef
            ref, data, ref_ept = update_LamRef(ref,lams,eps,data,ref_ept,endpts)
        for group in groups:
            lams = group[1]
            adjustLams2Ref(ref,lams)
        bndry_ids_all = set()
        for group in groups:
            group_ids, group_lams = group[:2]
            p, data, b_pairs, bndry_ids = update_Prob_Data(group_ids,shape,grid,
                                                           group_lams,eps,
                                                           p,eta_1,eta_2,
                                                           data)
            B_pairs += b_pairs
            bndry_ids_all |= bndry_ids
        for key,val in bnd_ind_sum_master.iteritems():
            _int = ind2int(key,shape)
            p[_int] *= val[0]/val[1]
        p = p/np.sum(p)
        i += 1
        avg = B_pairs/((q+1)*L*i)
        bndry_ids_master |= bndry_ids_all
    return ref, data, p, i, avg, bndry_ids_master, starts
