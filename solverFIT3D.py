import numpy as np
from scipy.constants import c as c_light, epsilon_0 as eps_0, mu_0 as mu_0
from scipy.sparse import csc_matrix as sparse_mat
from scipy.sparse import diags, block_diag, hstack, vstack
from scipy.sparse.linalg import inv
from field import Field

class SolverFIT3D:

    def __init__(self, grid, cfln=1.0,
                 bc_low=['Periodic', 'Periodic', 'Periodic'],
                 bc_high=['Periodic', 'Periodic', 'Periodic'],
                 use_conductors=True, use_materials=False,
                 i_s=0, j_s=0, k_s=0, N_pml_low=None, N_pml_high=None):

        # Grid 
        self.grid = grid
        self.cfln = cfln
        self.dt = cfln / (c_light * np.sqrt(1 / self.grid.dx ** 2 + 1 / self.grid.dy ** 2 +
                                            1 / self.grid.dz ** 2))
        self.use_conductors = use_conductors
        self.use_materials = use_materials

        self.Nx = self.grid.nx
        self.Ny = self.grid.ny
        self.Nz = self.grid.nz
        self.N = self.Nx*self.Ny*self.Nz

        self.dx = self.grid.dx
        self.dy = self.grid.dy
        self.dz = self.grid.dz

        self.L = self.grid.L
        self.iA = self.grid.iA
        self.tL = self.grid.tL
        self.itA = self.grid.itA

        # Fields
        self.E = Field(self.Nx, self.Ny, self.Nz)
        self.H = Field(self.Nx, self.Ny, self.Nz)
        self.J = Field(self.Nx, self.Ny, self.Nz)

        # Matrices
        N = self.N

        self.Px = diags([-1, 1], [0, 1], shape=(N, N), dtype=np.int8)
        self.Py = diags([-1, 1], [0, self.Nx], shape=(N, N), dtype=np.int8)
        self.Pz = diags([-1, 1], [0, self.Nx*self.Ny], shape=(N, N), dtype=np.int8)

        # original grid
        self.Ds = diags(self.L.toarray(), shape=(3*N, 3*N), dtype=float)
        self.iDa = diags(self.iA.toarray(), shape=(3*N, 3*N), dtype=float)

        # tilde grid
        self.tDs = diags(self.tL.toarray(), shape=(3*N, 3*N), dtype=float)
        self.itDa = diags(self.itA.toarray(), shape=(3*N, 3*N), dtype=float)

        # Curl matrix
        self.C = vstack([
                            hstack([sparse_mat((N,N)), -self.Pz, self.Py]),
                            hstack([self.Pz, sparse_mat((N,N)), -self.Px]),
                            hstack([-self.Py, self.Px, sparse_mat((N,N))])
                        ])
                
        # Boundaries
        self.bc_low = bc_low
        self.bc_high = bc_high
        self.apply_bc_to_C() 

        # Materials [TODO]
        self.ieps = Field(self.Nx, self.Ny, self.Nz, use_ones=True)*(1./eps_0) 
        self.imu = Field(self.Nx, self.Ny, self.Nz, use_ones=True)*(1./mu_0) 

        if use_materials:
            self.add_materials()

        if use_conductors:
            self.apply_conductors()

        self.iDeps = diags(self.ieps.toarray(), shape=(3*N, 3*N), dtype=float)
        self.iDmu = diags(self.imu.toarray(), shape=(3*N, 3*N), dtype=float)

        # Pre-computing
        self.tDsiDmuiDaC = self.tDs * self.iDmu * self.iDa * self.C 
        self.itDaiDepsDstC = self.itDa * self.iDeps * self.Ds * self.C.transpose()

        self.step_0 = True

    def one_step(self):

        if self.step_0:
            self.set_ghosts_to_0()
            self.step_0 = False

            if self.use_conductors:
                self.set_field_in_conductors_to_0()

        self.H.fromarray(self.H.toarray() -
                         self.dt*self.tDsiDmuiDaC*self.E.toarray()
                         )

        #compute J here ?

        self.E.fromarray(self.E.toarray() +
                         self.dt*(self.itDaiDepsDstC * self.H.toarray() - self.iDeps*self.J.toarray())
                         )
        
    def apply_bc_to_C(self):
        '''
        Modifies rows or columns of C and tDs and itDa matrices
        according to bc_low and bc_high
        '''

        # Perodic: out == in
        if any(True for x in self.bc_low if x.lower() == 'periodic'):
            if self.bc_low[0].lower() == 'periodic' and self.bc_high[0].lower() == 'periodic':
                self.tL[-1, :, :, 'x'] = self.L[0, :, :, 'x']
                self.itA[-1, :, :, 'y'] = self.iA[0, :, :, 'y']
                self.itA[-1, :, :, 'z'] = self.iA[0, :, :, 'z']

            elif self.bc_low[1].lower() == 'periodic' and self.bc_high[1].lower() == 'periodic':
                self.tL[:, -1, :, 'y'] = self.L[:, 0, :, 'y']
                self.itA[:, -1, :, 'x'] = self.iA[:, 0, :, 'x']
                self.itA[:, -1, :, 'z'] = self.iA[:, 0, :, 'z']

            elif self.bc_low[2].lower() == 'periodic' and self.bc_high[2].lower() == 'periodic':
                self.tL[:, :, -1, 'z'] = self.L[:, :, 0, 'z']
                self.itA[:, :, -1, 'x'] = self.iA[:, :, 0, 'x']
                self.itA[:, :, -1, 'y'] = self.iA[:, :, 0, 'y']
            else:
                raise Exception('Invalid use of periodic boundary condiions')

            self.tDs = diags(self.tL.toarray(), shape=(3*self.N, 3*self.N), dtype=float)
            self.itDa = diags(self.itA.toarray(), shape=(3*self.N, 3*self.N), dtype=float)

        # Dirichlet PEC: tangential E field = 0 at boundary
        if any(True for x in self.bc_low if x.lower() == 'electric' or x.lower() == 'pec'):
    
            if self.bc_low[0].lower() == 'electric' or self.bc_low[0].lower() == 'pec':
                xlo = 0
            if self.bc_low[1].lower() == 'electric' or self.bc_low[1].lower() == 'pec':
                ylo = 0    
            if self.bc_low[2].lower() == 'electric' or self.bc_low[2].lower() == 'pec':
                zlo = 0   
            if self.bc_high[0].lower() == 'electric' or self.bc_high[0].lower() == 'pec':
                xhi = 0
            if self.bc_high[1].lower() == 'electric' or self.bc_high[1].lower() == 'pec':
                yhi = 0
            if self.bc_high[2].lower() == 'electric' or self.bc_high[2].lower() == 'pec':
                zhi = 0

            # Assemble matrix
            self.BC = Field(self.Nx, self.Ny, self.Nz, dtype=np.int8, use_ones=True)

            for d in ['x', 'y', 'z']: #tangential to zero
                if d != 'x':
                    self.BC[0, :, :, d] = xlo
                    self.BC[-1, :, :, d] = xhi
                if d != 'y':
                    self.BC[:, 0, :, d] = ylo
                    self.BC[:, -1, :, d] = yhi
                if d != 'z':
                    self.BC[:, :, 0, d] = zlo
                    self.BC[:, :, -1, d] = zhi
            
            self.Dbc = diags(self.BC.toarray(),
                            shape=(3*self.N, 3*self.N), 
                            dtype=np.int8
                            )

            # Update C (columns)
            self.C = self.C*self.Dbc


        # Dirichlet PMC: tangential H field = 0 at boundary
        if any(True for x in self.bc_low if x.lower() == 'magnetic' or x.lower() == 'pmc'):

            if self.bc_low[0].lower() == 'magnetic' or self.bc_low[1] == 'pmc':
                xlo = 0
            if self.bc_low[1].lower() == 'magnetic' or self.bc_low[1] == 'pmc':
                ylo = 0    
            if self.bc_low[2].lower() == 'magnetic' or self.bc_low[2] == 'pmc':
                zlo = 0   
            if self.bc_high[0].lower() == 'magnetic' or self.bc_high[0] == 'pmc':
                xhi = 0
            if self.bc_high[1].lower() == 'magnetic' or self.bc_high[1] == 'pmc':
                yhi = 0
            if self.bc_high[2].lower() == 'magnetic' or self.bc_high[2] == 'pmc':
                zhi = 0

            # Assemble matrix
            self.BC = Field(self.Nx, self.Ny, self.Nz, dtype=np.int8, use_ones=True)

            for d in ['x', 'y', 'z']: #tangential to zero
                if d != 'x':
                    self.BC[0, :, :, d] = xlo
                    self.BC[-1, :, :, d] = xhi
                if d != 'y':
                    self.BC[:, 0, :, d] = ylo
                    self.BC[:, -1, :, d] = yhi
                if d != 'z':
                    self.BC[:, :, 0, d] = zlo
                    self.BC[:, :, -1, d] = zhi

            self.Dbc = diags(self.BC.toarray(),
                            shape=(3*self.N, 3*self.N), 
                            dtype=np.int8
                            )

            # Update C (rows)
            self.C = self.Dbc*self.C

    def set_ghosts_to_0(self):
        '''
        Cleanup for initial conditions if they are 
        accidentally applied to the ghost cells
        '''    
        # Set H ghost quantities to 0
        for d in ['x', 'y', 'z']: #tangential to zero
            if d != 'x':
                self.H[-1, :, :, d] = 0.
            if d != 'y':
                self.H[:, -1, :, d] = 0.
            if d != 'z':
                self.H[:, :, -1, d] = 0.

        # Set E ghost quantities to 0
        self.E[-1, :, :, 'x'] = 0.
        self.E[:, -1, :, 'y'] = 0.
        self.E[:, :, -1, 'z'] = 0.

    def apply_conductors(self):
        '''
        Set the 1/epsilon values inside the PEC conductors to zero
        '''
        self.flag_in_conductors = self.grid.flag_int_cell_yz[:-1,:,:]  \
                        * self.grid.flag_int_cell_zx[:,:-1,:] \
                        * self.grid.flag_int_cell_xy[:,:,:-1]

        self.ieps *= self.flag_in_conductors

    def set_field_in_conductors_to_0(self):
        '''
        Cleanup for initial conditions if they are 
        accidentally applied to the conductors
        '''    
        self.flag_cleanup = self.grid.flag_int_cell_yz[:-1,:,:]  \
                        + self.grid.flag_int_cell_zx[:,:-1,:] \
                        + self.grid.flag_int_cell_xy[:,:,:-1]

        self.H *= self.flag_cleanup
        self.E *= self.flag_cleanup
        



    def add_materials(self):
        '''
        [TODO]
        '''

        pass