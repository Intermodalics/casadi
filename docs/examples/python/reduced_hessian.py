#
#     This file is part of CasADi.
#
#     CasADi -- A symbolic framework for dynamic optimization.
#     Copyright (C) 2010-2014 Joel Andersson, Joris Gillis, Moritz Diehl,
#                             K.U. Leuven. All rights reserved.
#     Copyright (C) 2011-2014 Greg Horn
#
#     CasADi is free software; you can redistribute it and/or
#     modify it under the terms of the GNU Lesser General Public
#     License as published by the Free Software Foundation; either
#     version 3 of the License, or (at your option) any later version.
#
#     CasADi is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#     Lesser General Public License for more details.
#
#     You should have received a copy of the GNU Lesser General Public
#     License along with CasADi; if not, write to the Free Software
#     Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#
#
# -*- coding: utf-8 -*-
from casadi import *
import numpy as NP
import matplotlib.pyplot as plt

""" 
Example program demonstrating sensitivity analysis with sIPOPT from CasADi

Test problem (from sIPOPT example collection)

    min  (x1-1)^2 +(x2-2)^2 + (x3-3)^2
    s.t.    x1+2*x2+3*x3 = 0

@author Joel Andersson, K.U. Leuven 2012
"""

# Optimization variables
x = SX.sym("x",3)

# Objective
f = (x[0]-1)**2 + (x[1]-2)**2 + (x[2]-3)**2

# Constraint
g = x[0]+2*x[1]+3*x[2]

# Initial guess and bounds for the optimization variables
x0  = [25,0,0]
lbx = [-inf, -inf, -inf]
ubx = [ inf,  inf,  inf]

# Nonlinear bounds
lbg = [0.00]
ubg = [0.00]

# Create NLP
nlp = SXFunction("nlp", nlpIn(x=x), nlpOut(f=f, g=g))

# NLP solver options
opts = {}

# Mark the parameters amongst the variables (see sIPOPT documentation)
var_integer_md = {}
var_integer_md["red_hessian"] = [0,1,2]
opts["var_integer_md"] = var_integer_md

# Enable reduced hessian calculation
opts["compute_red_hessian"] = "yes"

# Create an NLP solver
solver = NlpSolver("solver", "ipopt", nlp, opts)

# Solve NLP
res = solver({"x0" : x0,
              "lbx" : lbx,
              "ubx" : ubx,
              "lbg" : lbg,
              "ubg" : ubg})

# Print the solution
print "----" 
print "Minimal cost " , res["f"] 
print "----" 

print "Solution" 
print "x = " , res["x"].nonzeros() 
print "----" 

# Obtain the reduced Hessian
try:
        red_hess = NP.array(solver.getReducedHessian())
        print "Reduced Hessian:"
        print red_hess
except:
        print "Support for retrieving the reduced Hessian not enabled."



