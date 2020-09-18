import numpy as np
from scipy.constants import c as c_light, epsilon_0 as eps_0, mu_0 as mu_0
import matplotlib
# matplotlib.use('Agg')
from matplotlib import pyplot as plt
from matplotlib import patches
import os
from tqdm import tqdm
from solver3D import EMSolver3D
from grid3D import Grid3D
from conductors3d import InCube, ConductorsAssembly, InSphere, Plane
from scipy.special import jv

Z0 = np.sqrt(mu_0 / eps_0)

L = 1.
# Number of mesh cells
N = 30
Nx = N
Ny = N
Nz = N
Lx = L
Ly = L
Lz = L
dx = L / Nx
dy = L / Ny
dz = L / Nz

LL = dx*8 - 0.1*dx

r_circ = 0.3
xmin = -Lx/2
xmax = Lx/2
ymin = -Ly/2
ymax = Ly/2
zmin = -Lz/2
zmax = Lz/2

lx = Lx - 2*LL
ly = Ly - 2*LL
lz = Lz - 2*LL
x_cent = 0
y_cent = 0
z_cent = 0
theta = np.pi/4

n1 = -np.array([np.cos(theta), np.sin(theta), 0])
n2 = -np.array([np.cos(theta + np.pi/2), np.sin(theta + np.pi/2), 0])
n3 = -np.array([np.cos(theta + np.pi), np.sin(theta + np.pi), 0])
n4 = -np.array([np.cos(theta + 3*np.pi/2), np.sin(theta + 3*np.pi/2), 0])
n5 = -np.array([0, 0, 1])
n6 = np.array([0, 0, 1])

R_theta = np.array([[np.cos(theta), - np.sin(theta), 0], [np.sin(theta), np.cos(theta), 0], [0, 0, 1]])
R_rect = np.array([[np.cos(np.pi/2), - np.sin(np.pi/2), 0], [np.sin(np.pi/2), np.cos(np.pi/2), 0], [0, 0, 1]])



p1 = np.dot(R_theta, np.array([lx/2, ly/2, 0]))
p2 = np.dot(R_theta, np.array([-lx/2, ly/2, 0]))
p3 = np.dot(R_theta, np.array([-lx/2, -ly/2, 0]))
p4 = np.dot(R_theta, np.array([lx/2, -ly/2, 0]))
p5 = np.array([0, 0, lz/2])
p6 = np.array([0, 0, -lz/2])

plane1 = Plane(p1, n1)
plane2 = Plane(p2, n2)
plane3 = Plane(p3, n3)
plane4 = Plane(p4, n4)
plane5 = Plane(p5, n5)
plane6 = Plane(p6, n6)

cube = InCube(lx, ly, lz, x_cent, y_cent, z_cent)
sphere = InSphere(r_circ, x_cent, y_cent, z_cent)
conductors = ConductorsAssembly([plane1, plane2, plane3, plane4, plane5, plane6])
#conductors = ConductorsAssembly([cube])

# conductors = cube
sol_type = 'ECT'


grid = Grid3D(xmin, xmax, ymin, ymax, zmin, zmax, Nx, Ny, Nz, conductors, sol_type)
i_s = int(Nx / 2)
j_s = int(Ny / 2)
k_s = int(Nz / 2)
NCFL = 1

flag_in_conductor = np.zeros((Nx, Ny, Nz), dtype=bool)

for ii in range(Nx):
    for jj in range(Ny):
        for kk in range(Nz):
            x = xmin + dx * ii
            y = ymin + dy * jj
            z = zmin + dz * kk
            flag_in_conductor[ii, jj, kk] = cube.in_conductor(x, y, z)

solver = EMSolver3D(grid, sol_type, NCFL, i_s, j_s, k_s)

# Constants
mu_r = 1
eps_r = 1

Nborrow = np.zeros((Nx, Ny))
Nlend = np.zeros((Nx, Ny))
minpatch = np.ones((Nx, Ny))
small_patch = np.ones((Nx, Ny), dtype=bool)
'''
Nborrow = np.zeros((Nx, Ny, Nz))
Nlend = np.zeros((Nx, Ny, Nz))

for ii in range(Nx):
    for jj in range(Ny):
        for kk in range(Nz):
            Nborrow[ii, jj, kk] = len(grid.borrowing_xy[ii, jj, kk])
            Nlend[ii, jj, kk] = len(grid.lending_xy[ii, jj, kk])
'''
m = 0
n = 1
p = 1


def analytic_sol_Hz(x, y, z, t):
    Rm = np.array([[np.cos(-theta), - np.sin(-theta), 0],[np.sin(-theta), np.cos(-theta), 0], [0, 0, 1]])
    [x_0, y_0, z_0] = np.dot(Rm, np.array([x, y, z]))

    return np.cos(m * np.pi / lx * (x_0 + xmin)) * np.cos(n * np.pi / ly * (y_0 + ymin + LL)) * np.sin(
        p * np.pi / lz * (z_0 + zmin + LL)) * np.cos(np.sqrt(2) * np.pi / lx * c_light * t)


h_2 = (m * np.pi / lx) ** 2 + (n * np.pi / ly) ** 2 + (p * np.pi / lz) ** 2


def analytic_sol_Hy(x, y, z, t):
    Rm = np.array([[np.cos(-theta), - np.sin(-theta), 0],[np.sin(-theta), np.cos(-theta), 0], [0, 0, 1]])
    [x_0, y_0, z_0] = np.dot(Rm, np.array([x, y, z]))
    return -2 / h_2 * (n * np.pi / ly) * (p * np.pi / lz ) * np.cos(m * np.pi / lx * (x_0 + xmin + LL)) * np.sin(
        n * np.pi / ly * (y_0 + ymin + LL)) * np.cos(p * np.pi / lz * (z_0 + zmin + LL)) * np.cos(
        np.sqrt(2) * np.pi / lx * c_light * t)
    # return -0.9994120256621584*np.cos(m*np.pi/lx*(x_0 + xmin))*np.sin(n*np.pi/ly*(y_0 + ymin))*np.cos(p*np.pi/lz*(z_0 + zmin))*np.cos(np.sqrt(2)*np.pi/lx*c_light*t)


def analytic_sol_Hx(x, y, z, t):
    Rm = np.array([[np.cos(-theta), - np.sin(-theta), 0],[np.sin(-theta), np.cos(-theta), 0], [0, 0, 1]])
    [x_0, y_0, z_0] = np.dot(Rm, np.array([x, y, z]))

    return -2 / h_2 * (m * np.pi / lx) * (p * np.pi / lz) * np.sin(m * np.pi / lx * (x_0 + xmin + LL)) * np.cos(
        n * np.pi / ly * (y_0 + ymin + LL)) * np.cos(p * np.pi / lz * (z_0 + zmin + LL)) * np.cos(
        np.sqrt(2) * np.pi / lx * c_light * t)


k = 2.7437 / r_circ

for ii in range(Nx):
    for jj in range(Ny):
        for kk in range(Nz):
            if grid.flag_int_cell_xy[ii, jj, kk]:  # and not grid.flag_bound_cell_xy[ii, jj, kk]:
                x = (ii + 0.5) * dx + xmin
                y = (jj + 0.5) * dy + ymin
                z = kk * dz + zmin
                solver.Hz[ii, jj, kk] = analytic_sol_Hz(x, y, z, -0.5 * solver.dt)

            if grid.flag_int_cell_zx[ii, jj, kk]:
                x = (ii + 0.5) * dx + xmin
                y = jj * dy + ymin
                z = (kk + 0.5) * dz + zmin
                solver.Hy[ii, jj, kk] = analytic_sol_Hy(x, y, z, -0.5 * solver.dt)

            if grid.flag_int_cell_yz[ii, jj, kk]:
                x = ii*dx + xmin
                y = (jj + 0.5)*dy + ymin
                z = (kk + 0.5)*dz + zmin
                solver.Hx[ii, jj, kk] = analytic_sol_Hx(x, y, z, -0.5 * solver.dt)


Nt = 0

res_Hy = np.zeros(Nt)
res_Ex = np.zeros(Nt)
res_Hz = np.zeros(Nt)

for t in tqdm(range(Nt)):

    fig, axs = plt.subplots(2, 3, figsize=(16, 10))
    fig.subplots_adjust(left=0.05, bottom=0.1, right=0.97, top=0.94, wspace=0.15)
    
    im1 = axs[0, 0].imshow(solver.Ex[i_s, :, :], cmap='jet', vmax=530, vmin=-530)  # ,extent=[0, L , 0, L ])
    axs[0, 0].set_xlabel('x [m]')
    axs[0, 0].set_ylabel('y [m]')
    axs[0, 0].set_title('Ex [V/m]')
    fig.colorbar(im1, ax=axs[0, 0], )
    im1 = axs[0, 1].imshow(solver.Ey[i_s, :, :], cmap='jet', vmax=530, vmin=-530)
    axs[0, 1].set_xlabel('x [m]')
    axs[0, 1].set_ylabel('y [m]')
    axs[0, 1].set_title('Ey [V/m]')
    fig.colorbar(im1, ax=axs[0, 1])
    im1 = axs[0, 2].imshow(solver.Ez[i_s, :, :], cmap='jet', vmax=530, vmin=-530)
    axs[0, 2].set_xlabel('x [m]')
    axs[0, 2].set_ylabel('y [m]')
    axs[0, 2].set_title('Ez [V/m]')
    fig.colorbar(im1, ax=axs[0, 2])
    im1 = axs[1, 0].imshow(solver.Hx[i_s, :, :], cmap='jet', vmax=1, vmin=-1)  # ,extent=[0, L , 0, L ])
    axs[1, 0].set_xlabel('x [m]')
    axs[1, 0].set_ylabel('y [m]')
    axs[1, 0].set_title('Hx [A/m]')
    fig.colorbar(im1, ax=axs[1, 0], )
    im1 = axs[1, 1].imshow(solver.Hy[i_s, :, :], cmap='jet', vmax=1, vmin=-1)
    axs[1, 1].set_xlabel('x [m]')
    axs[1, 1].set_ylabel('y [m]')
    axs[1, 1].set_title('Hy [A/m]')
    fig.colorbar(im1, ax=axs[1, 1])
    im1 = axs[1, 2].imshow(solver.Hz[i_s, :, :], cmap='jet', vmax=1, vmin=-1)
    axs[1, 2].set_xlabel('x [m]')
    axs[1, 2].set_ylabel('y [m]')
    axs[1, 2].set_title('Hz [A/m]')
    fig.colorbar(im1, ax=axs[1, 2])
    plt.suptitle(str(solver.time))
    
    folder = sol_type + '_images_cube'
    if not os.path.exists(folder):
        os.mkdir(folder)

    filename = folder + '/%d.png' % t
    plt.savefig(filename)
    plt.close(fig) 

    res_Hy[t] = solver.Hy[i_s, j_s, 5]
    res_Hz[t] = solver.Hz[i_s, 5, k_s]
    res_Ex[t] = solver.Ex[i_s, j_s, k_s]

    solver.one_step()
    # solver.Jx[i_s, j_s, k_s] = solver.gauss(solver.time)
    # solver.Hz[i_s, j_s, k_s] += solver.gauss(solver.time)
    # solver.Jz[i_s, j_s, k_s] = solver.gauss(solver.time)
'''
fig, axs = plt.subplots(2, 3, figsize=(16, 10))
fig.subplots_adjust(left=0.05, bottom=0.1, right=0.97, top=0.94, wspace=0.15)
axs[0, 0].imshow(grid.flag_int_cell_xy[:, :, k_s])
axs[0, 1].imshow(grid.Syz[:, :, k_s])
axs[0, 2].imshow(grid.Szx[:, :, k_s])
axs[1, 0].imshow(solver.Hz[:, :, k_s], cmap='jet')
axs[1, 1].imshow(solver.Hx[:, :, k_s], cmap='jet')
axs[1, 2].imshow(solver.Hy[:, :, k_s], cmap='jet')
'''
