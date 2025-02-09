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

from casadi import *
import casadi as c
from numpy import *
import numpy as n
import unittest
from types import *
from helpers import *
import copy

scipy_available = True
try:
	import scipy.special
	from scipy.linalg import expm
except:
	scipy_available = False
	
integrators = []

try:
  Integrator.loadPlugin("cvodes")
  integrators.append(("cvodes",["ode"],{"abstol": 1e-15,"reltol":1e-15,"fsens_err_con": True,"quad_err_con": False}))
except:
  pass
  
try:
  Integrator.loadPlugin("idas")
  integrators.append(("idas",["dae","ode"],{"abstol": 1e-15,"reltol":1e-15,"fsens_err_con": True,"calc_icB":True}))
except:
  pass

integrators.append(("collocation",["dae","ode"],{"implicit_solver":"kinsol","number_of_finite_elements": 18}))

try:
  Integrator.loadPlugin("oldcollocation")
  integrators.append(("oldcollocation",["dae","ode"],{"implicit_solver":"kinsol","number_of_finite_elements": 18,"startup_integrator":"idas"}))
  #integrators.append(("oldcollocation",["dae","ode"],{"implicit_solver":"nlp","number_of_finite_elements": 100,"startup_integrator":"cvodes","implicit_solver_options": {"nlp_solver": "ipopt","linear_solver_creator": "csparse"}}))
except:
  pass

integrators.append(("rk",["ode"],{"number_of_finite_elements": 1000}))

print "Will test these integrators:"
for cl, t, options in integrators:
  print cl, " : ", t

class Integrationtests(casadiTestCase):

  @slow()
  def test_full(self):
    num = self.num
    tc = DMatrix(n.linspace(0,num['tend'],100))
    
    t=SX.sym("t")
    q=SX.sym("q")
    p=SX.sym("p")
    
    out = SXFunction("out", daeIn(t=t, x=q, p=p),[q,t,p])
        
    f=SXFunction("f", daeIn(t=t, x=q, p=p),daeOut(ode=q/p*t**2))
    opts = {}
    opts["reltol"] = 1e-15
    opts["abstol"] = 1e-15
    opts["fsens_err_con"] = True
    #opts["verbose"] = True
    opts["t0"] = 0
    opts["tf"] = 2.3
    integrator = Integrator("integrator", "cvodes", f, opts)
    tf = 2.3
    
    solution = SXFunction("solution", integratorIn(x0=q, p=p),integratorOut(xf=q*exp(tf**3/(3*p))))
    
    for f in [solution,integrator]:
      f.setInput(0.3,"x0")
      f.setInput(0.7,"p")
    
    self.checkfunction(integrator,solution,digits=6)

  def test_tools_trivial(self):
    num = self.num

    x = SX.sym("x")
    p = SX.sym("p",0)
    tf = SX.sym("tf")
    f=SXFunction("f", [x,p], [x])
    
    for integrator in [
         simpleRK(f),
         simpleIRK(f),
         simpleIntegrator(f)
       ]:

      solution = SXFunction("solution", [x,p,tf],[x*exp(tf)], {"input_scheme":["x0","p","h"], "output_scheme":["xf"]})

      for f in [solution,integrator]:
        f.setInput(1,"x0")
        f.setInput(1,"h")
      integrator.evaluate()
      self.checkfunction(integrator,solution,digits=3)

  @slow()
  def test_tools(self):
    num = self.num

    t=SX.sym("t")
    q=SX.sym("q")
    p=SX.sym("p")
    t0=SX.sym("t0")
    q0=SX.sym("q0")
    f=SXFunction("f", [vertcat((q,t)),p],[vertcat((q/p*t**2,1))])
    for integrator in [
            simpleRK(f,500),
            simpleIRK(f,50),
            simpleIntegrator(f)
            ]:

      opts = {'input_scheme':["x0","p","h"], 'output_scheme':["xf"]}
      solution = SXFunction('solver', [vertcat((q0,t0)),p,t], [vertcat([q0*exp(((t0+t)**3-t0**3)/(3*p)),t0+t])], opts)
      
      for f in [solution,integrator]:
        f.setInput([0.3,0],"x0")
        f.setInput(0.7,"p")
        f.setInput(1, "h")
      
      self.checkfunction(integrator,solution,digits=3)
    
  @memory_heavy()
  def test_jac(self):
    self.message("Test exact jacobian #536")
    # This test is not automized, but works by inspection only.
    # To activate, recompile after ucnommenting the printout lines in cvodes.c, near "Used for validating casadi#536"
    #return
    DMatrix.setPrecision(18)

    tstart = SX.sym("tstart")
    tend = SX.sym("tend")
    
    integrators = [
              ("idas",["dae","ode"],{"abstol": 1e-9,"reltol":1e-9,"fsens_err_con": True,"calc_ic":True,"calc_icB":True}),
              ("cvodes",["ode"],{"abstol": 1e-5,"reltol":1e-5,"fsens_err_con": False,"quad_err_con": False})
              ]

    def variations(p_features, din, dout, rdin, rdout, *args):
      if "ode" in p_features:
        p_features_ = copy.copy(p_features)
        p_features_[p_features.index("ode")] = "dae"
        din_ = copy.copy(din)
        dout_ = copy.copy(dout)
        rdin_ = copy.copy(rdin)
        rdout_ = copy.copy(rdout)
        z = SX.sym("x", din_["x"].shape)
        din_["z"] = z
        dout_["ode"] = z
        dout_["alg"] = ( dout["ode"] - z) * (-0.8)
        if len(rdin_)>0:
          rz = SX.sym("rx", rdin_["rx"].shape)
          rdin_["rz"] = rz
          rdin_["z"] = z
          rdout_["ode"] = rz
          rdout_["alg"] = ( rdout["ode"] - rz) * (-0.7)
          
        yield (p_features, din, dout, rdin, rdout) + tuple(args)
        yield (p_features_, din_, dout_, rdin_, rdout_) + tuple(args)
      else:
        yield (p_features, din, dout, rdin, rdout) + tuple(args)
        
    def checks(): 
      Ns = 1
      
      x  = SX.sym("x")
      rx = SX.sym("rx")
      t = SX.sym("t")

      ti = (0,0.9995)
      pointA = {'x0': 1, 'rx0': 1}
      
      si = {'x0':x, 'rx0': rx}
      
      #sol = {'rxf': 1.0/(1-tend)}
      sol = {'rxf': rx*exp(tend), 'xf': x*exp(tend)}
     
      yield (["ode"],{'x':x,'t':t},{'ode':x},{'x':x,'rx':rx,'t':t},{'ode': rx},si,sol,pointA,ti)
      
      
    refXF = refRXF = None

    for tt in checks():
      for p_features, din, dout, rdin, rdout,  solutionin, solution, point, (tstart_, tend_) in variations(*tt):
        for Integrator, features, options in integrators:
          self.message(Integrator)
          x = SX.sym("x")
          dummyIntegrator = c.Integrator("dummyIntegrator", Integrator, SXFunction("dae", daeIn(x=x), daeOut(ode=x)))
          if p_features[0] in features:
            g = Function()
            if len(rdin)>1:
              g = SXFunction("g", rdaeIn(**rdin),rdaeOut(**rdout))
               
            f = SXFunction("f", daeIn(**din),daeOut(**dout))
            
            for k in solution.keys():
              solution[k] = substitute(solution[k],vertcat([tstart,tend]),vertcat([tstart_,tend_]))

            fs = SXFunction("fs", integratorIn(**solutionin),integratorOut(**solution))
              
          
            def itoptions(post=""):
              yield {"iterative_solver"+post: "gmres"}
              yield {"iterative_solver"+post: "bcgstab"}
              yield {"iterative_solver"+post: "tfqmr", "use_preconditionerB": True, "linear_solverB" : "csparse"} # Bug in Sundials? Preconditioning seems to be needed
             
            def solveroptions(post=""):
              yield {"linear_solver_type" +post: "dense" }
              allowedOpts = list(dummyIntegrator.getOptionAllowed("linear_solver_type" +post))
              #allowedOpts.remove("iterative") # disabled, see #1231
              if "iterative" in allowedOpts:
                  for it in itoptions(post):
                      d = {"linear_solver_type" +post: "iterative" }
                      d.update(it)
                      yield d
              if "banded" in allowedOpts:
                  yield {"linear_solver_type" +post: "banded" }
              yield {"linear_solver_type" +post: "user_defined", "linear_solver"+post: "csparse" }
                
            for a_options in solveroptions("B"):
              for f_options in solveroptions():
                message = "f_options: %s , a_options: %s" % (str(f_options) , str(a_options))
                print message
                opts = {}
                opts["exact_jacobianB"] = True
                opts["gather_stats"] = True
                #opts["verbose"] = True
                #opts["monitor"] = ["djacB","resB","djac","res"])
                opts["t0"] = tstart_
                opts["tf"] = tend_
                for op in (options, f_options, a_options):
                  for (k,v) in op.items():
                    opts[k] = v
                integrator = c.Integrator("integrator", Integrator, (f, g), opts)
                for ff in [fs,integrator]:
                  for k,v in point.items():
                    if not ff.getInput(k).isempty():
                      ff.setInput(v,k)

                integrator.evaluate()
                fs.evaluate()
                print "res=",integrator.getOutput("xf")-fs.getOutput("xf"), fs.getOutput("xf")
                print "Rres=",integrator.getOutput("rxf")-fs.getOutput("rxf"), fs.getOutput("rxf")
                # self.checkarray(integrator.getOutput("rxf"),fs.getOutput("rxf"),digits=4)
                stats = integrator.getStats()
                
                print stats
                self.assertTrue(stats["nsteps"]<1500)
                self.assertTrue(stats["nstepsB"]<2500)
                self.assertTrue(stats["nlinsetups"]<100)
                self.assertTrue(stats["nlinsetupsB"]<250)

  @memory_heavy()
  def test_lsolvers(self):
    self.message("Test different linear solvers")

    tstart = SX.sym("tstart")
    tend = SX.sym("tend")
    
    integrators = [
              ("idas",["dae","ode"],{"abstol": 1e-9,"reltol":1e-9,"fsens_err_con": True,"calc_ic":True,"calc_icB":True}),
              ("cvodes",["ode"],{"abstol": 1e-15,"reltol":1e-15,"fsens_err_con": True,"quad_err_con": False})
              ]
              
    def checks():  
      t=SX.sym("t")
      x=SX.sym("x")
      rx=SX.sym("rx")
      p=SX.sym("p")
      dp=SX.sym("dp")

      z=SX.sym("z")
      rz=SX.sym("rz")
      rp=SX.sym("rp")    
      solutionin = {'x0':x, 'p': p, 'rx0': rx,'rp' : rp}            
      pointA = {'x0':7.1,'p': 2, 'rx0': 0.13, 'rp': 0.127}
      ti = (0.2,2.3)
      yield (["dae"],{'x': x, 'z': z},{'alg': x-z, 'ode': z},{'x': x, 'z': z, 'rx': rx, 'rz': rz},{'alg': x-rz, 'ode': rz},solutionin,{'rxf': rx+x*(exp(tend-tstart)-1), 'xf':x*exp(tend-tstart)},pointA,ti)
      if not(args.run_slow): return
      yield (["dae"],{'x': x, 'z': z},{'alg': x-z, 'ode': z},{'x': x, 'z': z, 'rx': rx, 'rz': rz},{'alg': rx-rz, 'ode': rz},solutionin,{'rxf': rx*exp(tend-tstart), 'xf':x*exp(tend-tstart)},pointA,ti)
      yield (["ode"],{'x': x},{'ode': x},{'x': x,'rx': rx},{'ode': x},solutionin,{'rxf': rx+x*(exp(tend-tstart)-1), 'xf':x*exp(tend-tstart)},pointA,ti)
      yield (["ode"],{'x': x},{'ode': x},{'x': x,'rx': rx},{'ode': rx},solutionin,{'rxf': rx*exp(tend-tstart), 'xf':x*exp(tend-tstart)},pointA,ti)
      
      A=array([1,0.1])
      p0 = 1.13

      q=SX.sym("y",2,1)
      y0=q[0]
      yc0=dy0=q[1]
      p=SX.sym("p",1,1)

      s1=(2*y0-log(yc0**2/p+1))/2-log(cos(arctan(yc0/sqrt(p))+sqrt(p)*(tend-tstart)))
      s2=sqrt(p)*tan(arctan(yc0/sqrt(p))+sqrt(p)*(tend-tstart))
      yield (["ode"],{'x':q,'p':p},{'ode': vertcat([q[1],p[0]+q[1]**2 ])},{},{},{'x0':q, 'p': p} ,{'xf': vertcat([s1,s2])},{'x0': A, 'p': p0},(0,0.4) )

    for p_features, din, dout, rdin, rdout, solutionin, solution, point, (tstart_, tend_) in checks():

      for Integrator, features, options in integrators:
        self.message(Integrator)
        x = SX.sym("x")
        dummyIntegrator = c.Integrator("dummyIntegrator", Integrator, SXFunction("dae", daeIn(x=x), daeOut(ode=x)))
        if p_features[0] in features:
          g = Function()
          if len(rdin)>1:
            g = SXFunction("g", rdaeIn(**rdin),rdaeOut(**rdout))
             
          f = SXFunction("f", daeIn(**din),daeOut(**dout))
            
          for k in solution.keys():
            solution[k] = substitute(solution[k],vertcat([tstart,tend]),vertcat([tstart_,tend_]))
          
          fs = SXFunction("fs", integratorIn(**solutionin),integratorOut(**solution))
        
          def itoptions(post=""):
            yield {"iterative_solver"+post: "gmres"}
            yield {"iterative_solver"+post: "bcgstab"}
            yield {"iterative_solver"+post: "tfqmr", "use_preconditionerB": True, "linear_solverB" : "csparse"} # Bug in Sundials? Preconditioning seems to be needed
           
          def solveroptions(post=""):
            yield {"linear_solver_type" +post: "dense" }
            allowedOpts = list(dummyIntegrator.getOptionAllowed("linear_solver_type" +post))
            #allowedOpts.remove("iterative")  # disabled, see #1231
            if "iterative" in allowedOpts:
                for it in itoptions(post):
                    d = {"linear_solver_type" +post: "iterative" }
                    d.update(it)
                    yield d
            if "banded" in allowedOpts:
                yield {"linear_solver_type" +post: "banded" }
            yield {"linear_solver_type" +post: "user_defined", "linear_solver"+post: "csparse" }
              
          for a_options in solveroptions("B"):
            for f_options in solveroptions():
              message = "f_options: %s , a_options: %s" % (str(f_options) , str(a_options))
              print message

              opts = {}
              opts["exact_jacobianB"] = True
              opts["t0"] = tstart_
              opts["tf"] = tend_
              for op in (options, f_options, a_options):
                 for (k,v) in op.items():
                    opts[k] = v
              integrator = c.Integrator("integrator", Integrator, (f, g), opts)
              
              for ff in [fs,integrator]:
                for k,v in point.items():
                  if not ff.getInput(k).isempty():
                    ff.setInput(v,k)

              integrator.evaluate()
              
              self.checkfunction(integrator,fs,gradient=False,hessian=False,sens_der=False,evals=False,digits=4,digits_sens=4,failmessage=message,verbose=False)
              
              


  @memory_heavy()
  def test_X(self):
    self.message("Extensive integrator tests")
    
    num=self.num
    tstart = SX.sym("tstart")
    tend = SX.sym("tstart")

    
    for Integrator, features, options in integrators:
      self.message(Integrator)
        
        
      def variations(p_features, din, dout, rdin, rdout, *args):
        if "ode" in p_features:
          p_features_ = copy.copy(p_features)
          p_features_[p_features.index("ode")] = "dae"
          din_ = copy.copy(din)
          dout_ = copy.copy(dout)
          rdin_ = copy.copy(rdin)
          rdout_ = copy.copy(rdout)
          z = SX.sym("x", din_["x"].shape)
          din_["z"] = z
          dout_["ode"] = z
          dout_["alg"] = ( dout["ode"] - z) * (-0.8)
          if len(rdin_)>0:
            rz = SX.sym("rx", rdin_["rx"].shape)
            rdin_["rz"] = rz
            rdin_["z"] = z
            rdout_["ode"] = rz
            rdout_["alg"] = ( rdout["ode"] - rz) * (-0.7)
            
          yield (p_features, din, dout, rdin, rdout) + tuple(args)
          yield (p_features_, din_, dout_, rdin_, rdout_) + tuple(args)
        else:
          yield (p_features, din, dout, rdin, rdout) + tuple(args)
        
      def checks():
        x0=num['q0']
        p_=num['p']
        rx0_= 0.13
        t=SX.sym("t")
        x=SX.sym("x")
        rx=SX.sym("rx")
        p=SX.sym("p")
        dp=SX.sym("dp")

        z=SX.sym("z")
        rz=SX.sym("rz")
        rp=SX.sym("rp")
        
        si = {'x0':x, 'p': p, 'rx0': rx,'rp' : rp}            
        pointA = {'x0':x0,'p': p_, 'rx0': rx0_, 'rp': 0.127}
        
        ti = (0.2,num['tend'])
        yield (["ode"],{'x':x},{'ode': 0},{},{},si,{'xf':x},pointA,ti)
        yield (["ode"],{'x':x},{'ode': 1},{},{},si,{'xf':x+(tend-tstart)},pointA,ti)
        yield (["ode"],{'x':x},{'ode': x},{},{},si,{'xf':x*exp(tend-tstart)},pointA,ti)
        yield (["ode"],{'x':x,'t':t},{'ode': t},{},{},si,{'xf':x+(tend**2/2-tstart**2/2)},pointA,ti)
        yield (["ode"],{'x':x,'t':t},{'ode': x*t},{},{},si,{'xf':x*exp(tend**2/2-tstart**2/2)},pointA,ti)
        yield (["ode"],{'x':x,'p':p},{'ode': x/p},{},{},si,{'xf':x*exp((tend-tstart)/p)},pointA,ti)
        if not(args.run_slow): return
        yield (["ode"],{'x':x},{'ode': x,'quad':0},{},{},si,{'qf':0},pointA,ti)
        yield (["ode"],{'x':x},{'ode': x,'quad':1},{},{},si,{'qf':(tend-tstart)},pointA,ti)
        yield (["ode"],{'x':x},{'ode': 0,'quad':x},{},{},si,{'qf':x*(tend-tstart)},pointA,ti)
        #yield ({'x':x},{'ode': 1,'quad':x},{'qf':(x-tstart)*(tend-tstart)+(tend**2/2-tstart**2/2)}), # bug in cvodes quad_err_con
        yield (["ode"],{'x':x},{'ode': x,'quad':x},{},{},si,{'qf':x*(exp(tend-tstart)-1)},pointA,ti)
        yield (["ode"],{'x':x,'t':t},{'ode': x,'quad':t},{},{},si,{'qf':(tend**2/2-tstart**2/2)},pointA,ti)
        yield (["ode"],{'x':x,'t':t},{'ode': x,'quad':x*t},{},{},si,{'qf':x*(exp(tend-tstart)*(tend-1)-(tstart-1))},pointA,ti)
        yield (["ode"],{'x':x,'p':p},{'ode': x,'quad':x/p},{},{},si,{'qf':x*(exp((tend-tstart))-1)/p},pointA,ti)
        yield (["ode"],{'x':x},{'ode':x},{'x':x,'rx':rx},{'ode':SX(0)},si,{'rxf': rx},pointA,ti)
        yield (["ode"],{'x':x},{'ode':x},{'x':x,'rx':rx},{'ode':SX(1)},si,{'rxf': rx+tend-tstart},pointA,ti)
        yield (["ode"],{'x':x,'t':t},{'ode':x},{'x':x,'rx':rx,'t':t},{'ode':t},si,{'rxf': rx+tend**2/2-tstart**2/2},pointA,ti)
        yield (["ode"],{'x':x},{'ode':x},{'x':x,'rx':rx},{'ode':rx},si,{'rxf': rx*exp(tend-tstart)},pointA,ti)
        yield (["ode"],{'x':x},{'ode':x},{'x':x,'rx':rx},{'ode':x},si,{'rxf': rx+x*(exp(tend-tstart)-1)},pointA,ti)
        yield (["ode"],{'x':x,'t':t},{'ode':x},{'x':x,'rx':rx,'t':t},{'ode':x*t},si,{'rxf': rx+x*(exp(tend-tstart)*(tend-1)-(tstart-1))},pointA,ti)
        yield (["ode"],{'x':x,'t':t},{'ode':x},{'x':x,'rx':rx,'t':t},{'ode':rx*t},si,{'rxf': rx*exp(tend**2/2-tstart**2/2)},pointA,ti)
        yield (["ode"],{'x':x},{'ode':x},{'x':x,'rx':rx},{'ode':rx, 'quad': 0},si,{'rqf': 0},pointA,ti)
        yield (["ode"],{'x':x},{'ode':x},{'x':x,'rx':rx},{'ode':rx, 'quad': 1},si,{'rqf': (tend-tstart)},pointA,ti)
        yield (["ode"],{'x':x},{'ode':x},{'x':x,'rx':rx},{'ode':rx, 'quad': rx},si,{'rqf': rx*(exp(tend-tstart)-1)},pointA,ti)
        yield (["ode"],{'x':x},{'ode':x},{'x':x,'rx':rx},{'ode':rx, 'quad': x},si,{'rqf': x*(exp(tend-tstart)-1)},pointA,ti)
        yield (["ode"],{'x':x,'t':t},{'ode':x},{'x':x,'rx':rx,'t':t},{'ode':rx, 'quad': t},si,{'rqf': (tend**2/2-tstart**2/2)},pointA,ti)
        yield (["ode"],{'x':x,'t':t},{'ode':x},{'x':x,'rx':rx,'t':t},{'ode':rx, 'quad': x*t},si,{'rqf': x*(exp(tend-tstart)*(tend-1)-(tstart-1))},pointA,ti)
        yield (["ode"],{'x':x,'t':t},{'ode':x},{'x':x,'rx':rx,'t':t},{'ode':rx, 'quad': rx*t},si,{'rqf': rx*(exp(tend-tstart)*(tstart+1)-(tend+1))},pointA,ti) # this one is special: integrate(t*rx*exp(tf-t),t,t0,tf)
        yield (["ode"],{'x':x,'p':p},{'ode':x},{'x':x,'rx':rx,'p':p},{'ode':rx, 'quad': p},si,{'rqf': p*(tend-tstart)},pointA,ti)
        yield (["ode"],{'x':x,'p':p},{'ode':x},{'x':x,'rx':rx,'p':p,'rp':rp},{'ode':rx, 'quad': rp},si,{'rqf': rp*(tend-tstart)},pointA,ti)
        yield (["ode"],{'x':x,'t':t},{'ode':x},{'x':x,'rx':rx,'t':t},{'ode':rx*t},si,{'rxf': rx*exp(tend**2/2-tstart**2/2)},pointA,ti)
        yield (["ode"],{'x':x,'t':t},{'ode':x},{'x':x,'rx':rx,'t':t},{'ode':x*t},si,{'rxf': rx+x*(exp(tend-tstart)*(tend-1)-(tstart-1))},pointA,ti)
        yield (["dae"],{'x':x,'z':z},{'ode':z,'alg': -0.8*(z-x),'quad': z},{},{},si,{'qf':x*(exp(tend-tstart)-1)},pointA,ti)
        yield (["dae"],{'x':x,'z':z},{'ode':z,'alg': -0.8*(z-x)},{'x':x,'rx':rx,'rz': rz,'z':z},{'ode':rz, 'alg': -0.7*(rz-rx), 'quad': rz},si,{'rqf': rx*(exp(tend-tstart)-1)},pointA,ti)
        yield (["dae"],{'x':x,'z':z},{'ode':z,'alg': -0.8*(z-x)},{'x':x,'rx':rx,'rz': rz,'z':z},{'ode':rz, 'alg': -0.7*(rz-rx), 'quad': z},si,{'rqf': x*(exp(tend-tstart)-1)},pointA,ti)
        
        
        A=array([1,0.1])
        p0 = 1.13

        q=SX.sym("y",2,1)
        y0=q[0]
        yc0=dy0=q[1]
        p=SX.sym("p",1,1)
        
        s1=(2*y0-log(yc0**2/p+1))/2-log(cos(arctan(yc0/sqrt(p))+sqrt(p)*(tend-tstart)))
        s2=sqrt(p)*tan(arctan(yc0/sqrt(p))+sqrt(p)*(tend-tstart))
        yield (["ode"],{'x':q,'p':p},{'ode': vertcat([q[1],p[0]+q[1]**2 ])},{},{},{'x0':q, 'p': p} ,{'xf': vertcat([s1,s2])},{'x0': A, 'p': p0},(0,0.4) )
      
      for tt in checks():
        print tt
        for p_features, din, dout, rdin, rdout, solutionin, solution, point, (tstart_, tend_) in variations(*tt):
          if p_features[0] in features:
            message = "%s: %s => %s, %s => %s, explicit (%s) tstart = %f" % (Integrator,str(din),str(dout),str(rdin),str(rdout),str(solution),tstart_)
            print message
            g = Function()
            if len(rdin)>1:
              g = SXFunction("g", rdaeIn(**rdin),rdaeOut(**rdout))
               
            dout_sx = {k:SX(v) for k, v in dout.iteritems()} # hack
            f = SXFunction("f", daeIn(**din),daeOut(**dout_sx))
            
            for k in solution.keys():
              solution[k] = substitute(solution[k],vertcat([tstart,tend]),vertcat([tstart_,tend_]))
            
            fs = SXFunction("fs", integratorIn(**solutionin),integratorOut(**solution))

            opts = dict(options)
            opts["t0"] = tstart_
            if Integrator in ('cvodes', 'idas'):
              opts["abstol"] = 1e-9
              opts["reltol"] = 1e-9
            opts["tf"] = tend_
            if Integrator=='idas':
              opts["init_xdot"] = list(DMatrix(point["x0"]))
              opts["calc_icB"] = True
              opts["augmented_options"] = {"init_xdot":None, "abstol":1e-9,"reltol":1e-9}
            integrator = c.Integrator("integrator", Integrator, (f, g), opts)

            for ff in [fs,integrator]:
              for k,v in point.items():
                if not ff.getInput(k).isempty():
                  ff.setInput(v,k)
            integrator.evaluate()
            
            self.checkfunction(integrator,fs,gradient=False,hessian=False,sens_der=False,evals=False,digits=4,digits_sens=4,failmessage=message,verbose=False)

        
  def setUp(self):
    # Reference solution is x0 e^((t^3-t0^3)/(3 p))
    t=SX.sym("t")
    x=SX.sym("x")
    p=SX.sym("p")
    f=SXFunction("f", daeIn(t=t, x=x, p=p),daeOut(ode=x/p*t**2))
    opts = {}
    opts["reltol"] = 1e-15
    opts["abstol"] = 1e-15
    opts["fsens_err_con"] = True
    #opts["verbose"] = True
    opts["t0"] = 0
    opts["tf"] = 2.3
    integrator = Integrator("integrator", "cvodes", f, opts)
    q0   = MX.sym("q0")
    par  = MX.sym("p")
    
    qend = integrator({'x0':q0, 'p':par})["xf"]
    
    qe=MXFunction("qe", [q0,par],[qend])
    self.integrator = integrator
    self.qe=qe
    self.qend=qend
    self.q0=q0
    self.par=par
    self.f = f
    self.num={'tend':2.3,'q0':7.1,'p':2}
    pass
            
  def test_eval2(self):
    self.message('CVodes integration: evaluation with MXFunction indirection')
    num=self.num
    qend=self.qend
    
    par=self.par
    q0=self.q0
    qe=MXFunction("qe", [q0,par],[qend[0]])
    
    f = MXFunction("f", [q0],qe.call([q0,MX(num['p'])]))
    f.setInput([num['q0']],0)
    f.evaluate()

    tend=num['tend']
    q0=num['q0']
    p=num['p']
    self.assertAlmostEqual(f.getOutput()[0],q0*exp(tend**3/(3*p)),9,"Evaluation output mismatch")
  
  def test_issue92c(self):
    self.message("regression check for issue 92")
    t=SX.sym("t")
    x=SX.sym("x")
    y=SX.sym("y")
    z=x*exp(t)
    f=SXFunction("f", daeIn(t=t, x=vertcat([x,y])),[vertcat([z,z])])
    # Pass inputs
    f.setInput(1.0,"t")
    f.setInput([1.0,0.0],"x")
    # Evaluate 
    f.evaluate()
    # print result
    print f.getOutput()
  
  def test_issue92b(self):
    self.message("regression check for issue 92")
    t=SX.sym("t")
    x=SX.sym("x")
    y=SX.sym("y")
    f=SXFunction("f", daeIn(t=t, x=vertcat([x,y])),daeOut(ode=vertcat([x,(1+1e-9)*x])))
    opts = {}
    opts["fsens_err_con"] = True
    opts["t0"] = 0
    opts["tf"] = 1
    integrator = Integrator("integrator", "cvodes", f, opts)

    # Pass inputs
    integrator.setInput([1,0],"x0")
    ## Integrate
    integrator.evaluate()
    # print result
    print integrator.getOutput("xf")
    
  def test_issue92(self):
    self.message("regression check for issue 92")
    t=SX.sym("t")
    x=SX.sym("x")
    var = MX.sym("var",2,1)

    q = vertcat([x,SX.sym("problem")])

    dq=vertcat([x,x])
    f=SXFunction("f", daeIn(t=t,x=q),daeOut(ode=dq))
    opts = {}
    opts["fsens_err_con"] = True
    opts["reltol"] = 1e-12
    opts["t0"] = 0
    opts["tf"] = 1
    integrator = Integrator("integrator", "cvodes", f, opts)

    qend = integrator({'x0':var})["xf"]

    f = MXFunction("f", [var],[qend[0]])

    J=f.jacobian(0)
    J.setInput([1,0])
    J.evaluate()
    print "jac=",J.getOutput().nz[0]-exp(1)
    self.assertAlmostEqual(J.getOutput()[0,0],exp(1),5,"Evaluation output mismatch")
    
  def test_eval(self):
    self.message('CVodes integration: evaluation')
    num=self.num
    qe=self.qe
    qe.setInput([num['q0']],0)
    qe.setInput([num['p']],1)
    qe.evaluate()

    tend=num['tend']
    q0=num['q0']
    p=num['p']
    self.assertAlmostEqual(qe.getOutput()[0],q0*exp(tend**3/(3*p)),9,"Evaluation output mismatch")
    
    
  def test_jac1(self):
    self.message('CVodes integration: jacobian to q0')
    num=self.num
    J=self.qe.jacobian(0)
    J.setInput([num['q0']],0)
    J.setInput([num['p']],1)
    J.evaluate()
    tend=num['tend']
    q0=num['q0']
    p=num['p']
    self.assertAlmostEqual(J.getOutput()[0],exp(tend**3/(3*p)),9,"Evaluation output mismatch")
    
  def test_jac2(self):
    self.message('CVodes integration: jacobian to p')
    num=self.num
    J=self.qe.jacobian(1)
    J.setInput([num['q0']],0)
    J.setInput([num['p']],1)
    J.evaluate()
    tend=num['tend']
    q0=num['q0']
    p=num['p']
    self.assertAlmostEqual(J.getOutput()[0],-(q0*tend**3*exp(tend**3/(3*p)))/(3*p**2),9,"Evaluation output mismatch")
    
  def test_bug_repeat(self):
    num={'tend':2.3,'q0':[0,7.1,7.1],'p':2}
    self.message("Bug that appears when rhs contains repeats")
    A=array([1,0.1,1])
    p0 = 1.13
    y0=A[0]
    yc0=dy0=A[1]
    te=0.4

    t=SX.sym("t")
    q=SX.sym("y",3,1)
    p=SX.sym("p")

    dh = p+q[0]**2
    f=SXFunction("f", daeIn(x=q,p=p,t=t),daeOut(ode=vertcat([dh ,q[0],dh])))

    opts = {}
    opts["reltol"] = 1e-15
    opts["abstol"] = 1e-15
    #opts["verbose"] = True
    opts["fsens_err_con"] = True
    opts["steps_per_checkpoint"] = 10000
    opts["t0"] = 0
    opts["tf"] = te
    integrator = Integrator("integrator", "cvodes", f, opts)

    q0   = MX.sym("q0",3,1)
    par  = MX.sym("p",1,1)
    qend = integrator({'x0':q0, 'p':par})["xf"]
    qe=MXFunction("qe", [q0,par],[qend])

    #J=self.qe.jacobian(2)
    J=qe.jacobian(0)
    J.setInput(A,0)
    J.setInput(p0,1)
    J.evaluate()
    outA=J.getOutput().toArray()
    f=SXFunction("f", daeIn(x=q,p=p,t=t),daeOut(ode=vertcat([dh ,q[0],(1+1e-9)*dh])))
    
    opts = {}
    opts["reltol"] = 1e-15
    opts["abstol"] = 1e-15
    #opts["verbose"] = True
    opts["fsens_err_con"] = True
    opts["steps_per_checkpoint"] = 10000
    opts["t0"] = 0
    opts["tf"] = te
    integrator = Integrator("integrator", "cvodes", f, opts)

    q0   = MX.sym("q0",3,1)
    par  = MX.sym("p",1,1)
    qend = integrator({'x0':q0, 'p':par})["xf"]
    qe=MXFunction("qe", [q0,par],[qend])

    #J=self.qe.jacobian(2)
    J=qe.jacobian(0)
    J.setInput(A,0)
    J.setInput(p0,1)
    J.evaluate()
    outB=J.getOutput().toArray()
    print outA-outB
    
  def test_hess3(self):
    self.message('CVodes integration: hessian to p: Jacobian of integrator.jacobian')
    num=self.num
    J=self.integrator.jacobian("p","xf")
    H=J.jacobian("p")
    H.setInput([num['q0']],"x0")
    H.setInput([num['p']],"p")
    H.evaluate()
    num=self.num
    tend=num['tend']
    q0=num['q0']
    p=num['p']
    self.assertAlmostEqual(H.getOutput()[0],(q0*tend**6*exp(tend**3/(3*p)))/(9*p**4)+(2*q0*tend**3*exp(tend**3/(3*p)))/(3*p**3),9,"Evaluation output mismatch")

  def test_hess4(self):
    self.message('CVodes integration: hessian to p: Jacobian of integrator.jacobian indirect')
    num=self.num
    J=self.integrator.jacobian("p","xf")
    
    q0=MX.sym("q0")
    p=MX.sym("p")
    Ji = MXFunction("Ji", [q0,p],(J({'x0':q0,'p':p}), J.outputScheme()))
    H=Ji.jacobian(1)
    H.setInput([num['q0']],0)
    H.setInput([num['p']],1)
    H.evaluate()
    num=self.num
    tend=num['tend']
    q0=num['q0']
    p=num['p']
    self.assertAlmostEqual(H.getOutput()[0],(q0*tend**6*exp(tend**3/(3*p)))/(9*p**4)+(2*q0*tend**3*exp(tend**3/(3*p)))/(3*p**3),9,"Evaluation output mismatch")

  def test_hess5(self):
    self.message('CVodes integration: hessian to p in an MX tree')
    num=self.num
    q0=MX.sym("q0")
    p=MX.sym("p")
    qe = MXFunction("qe", [q0,p],integratorOut(**self.integrator({'x0':q0,'p':p})))

    JT = MXFunction("JT", [q0,p],[qe.jac(1,0)[0].T])
    JT.setInput([num['q0']],0)
    JT.setInput([num['p']],1)
    JT.evaluate()
    print JT.getOutput()

    H  = JT.jacobian(1)
    H.setInput([num['q0']],0)
    H.setInput([num['p']],1)
    H.evaluate()
    tend=num['tend']
    q0=num['q0']
    p=num['p']
    self.assertAlmostEqual(H.getOutput()[0],(q0*tend**6*exp(tend**3/(3*p)))/(9*p**4)+(2*q0*tend**3*exp(tend**3/(3*p)))/(3*p**3),9,"Evaluation output mismatch")
    
  def test_hess6(self):
    self.message('CVodes integration: hessian to p in an MX tree')
    num=self.num
    q0=MX.sym("q0")
    p=MX.sym("p")
    qe = MXFunction("qe", [q0,p],integratorOut(**self.integrator({'x0':q0,'p':p})))
    
    H = qe.hessian(1)
    H.setInput([num['q0']],0)
    H.setInput([num['p']],1)
    H.evaluate()
    num=self.num
    tend=num['tend']
    q0=num['q0']
    p=num['p']
    self.assertAlmostEqual(H.getOutput()[0],(q0*tend**6*exp(tend**3/(3*p)))/(9*p**4)+(2*q0*tend**3*exp(tend**3/(3*p)))/(3*p**3),9,"Evaluation output mismatch")
     
  def test_glibcbug(self):
    self.message("former glibc error")
    A=array([2.3,4.3,7.6])
    B=array([[1,2.3,4],[-2,1.3,4.7],[-2,6,9]])

    te=0.7
    t=SX.sym("t")
    q=SX.sym("q",3,1)
    p=SX.sym("p",9,1)
    f_in = daeIn(t=t, x=q, p=p)
    f_out = daeOut(ode=mul(c.reshape(p,3,3),q))
    f=SXFunction("f", f_in,f_out)
    opts = {}
    opts["fsens_err_con"] = True
    opts["steps_per_checkpoint"] = 1000
    opts["t0"] = 0
    opts["tf"] = te
    integrator = Integrator("integrator", "cvodes", f, opts)
    q0   = MX.sym("q0",3,1)
    par  = MX.sym("p",9,1)
    qend = integrator({'x0':q0, 'p':par})["xf"]
    qe=integrator.jacobian("p","xf")
    qe = qe({'x0':q0,'p':par})['jac']
    qef=MXFunction("qef", [q0,par],[qe])

    qef.setInput(A,0)
    qef.setInput(B.ravel(),1)
    qef.evaluate()
    
  def test_linear_system(self):
    self.message("Linear ODE")
    if not(scipy_available):
        return
    A=array([2.3,4.3,7.6])
    B=array([[1,2.3,4],[-2,1.3,4.7],[-2,6,9]])
    te=0.7
    Be=expm(B*te)
    t=SX.sym("t")
    q=SX.sym("q",3,1)
    p=SX.sym("p",9,1)

    f=SXFunction("f", daeIn(t=t,x=q,p=p),daeOut(ode=mul(c.reshape(p,3,3),q)))
    opts = {}
    opts["fsens_err_con"] = True
    opts["reltol"] = 1e-15
    opts["abstol"] = 1e-15
    #opts["verbose"] = True
    opts["steps_per_checkpoint"] = 10000
    opts["t0"] = 0
    opts["tf"] = te
    integrator = Integrator("integrator", "cvodes", f, opts)

    q0   = MX.sym("q0",3,1)
    par  = MX.sym("p",9,1)
    qend = integrator({'x0':q0, 'p':par})["xf"]
    qe=MXFunction("qe", [q0,par],[qend])
    qendJ=integrator.jacobian("x0","xf")
    qendJ = qendJ({'x0':q0,'p':par})['jac']

    qeJ=MXFunction("qeJ", [q0,par],[qendJ])

    qendJ2=integrator.jacobian("x0","xf")
    qendJ2 = qendJ2({'x0':q0,'p':par})['jac']

    qeJ2=MXFunction("qeJ2", [q0,par],[qendJ2])
    
    qe.setInput(A,0)
    qe.setInput(vec(B),1)
    qe.evaluate()
    self.checkarray(dot(Be,A)/1e3,qe.getOutput()/1e3,"jacobian('x0','xf')")
    qeJ.setInput(A,0)
    qeJ.setInput(vec(B),1)
    qeJ.evaluate()
    self.checkarray(qeJ.getOutput()/1e3,Be/1e3,"jacobian('x0','xf')")
    
    
    qeJ2.setInput(A,0)
    qeJ2.setInput(vec(B),1)
    qeJ2.evaluate()
    
    return # this should return identical zero
    H=qeJ.jacobian(0,0)
    #H.setOption("ad_mode","reverse")
    H.setInput(A,0)
    H.setInput(vec(B),1)
    H.evaluate()
    print array(H.getOutput())
    
    
  def test_mathieu_system(self):
    self.message("Mathieu ODE")
    A=array([0.3,1.2])
    B=array([1.3,4.3,2.7])
    te=0.7

    t=SX.sym("t")
    q=SX.sym("q",2,1)
    p=SX.sym("p",3,1)

    f=SXFunction("f", daeIn(x=q,p=p,t=t),daeOut(ode=vertcat([q[1],(p[0]-2*p[1]*cos(2*p[2]))*q[0]])))
    opts = {}
    opts["fsens_err_con"] = True
    opts["reltol"] = 1e-15
    opts["abstol"] = 1e-15
    #opts["verbose"] = True
    opts["steps_per_checkpoint"] = 10000
    opts["t0"] = 0
    opts["tf"] = te
    integrator = Integrator("integrator", "cvodes", f, opts)

    q0   = MX.sym("q0",2,1)
    par  = MX.sym("p",3,1)
    qend = integrator({'x0':q0, 'p':par})["xf"]
    qe=MXFunction("qe", [q0,par],[qend])
    qendJ=integrator.jacobian("x0","xf")
    qendJ =qendJ({'x0':q0,'p':par})['jac']
    qeJ=MXFunction("qeJ", [q0,par],[qendJ])

    qe.setInput(A,0)
    qe.setInput(B,1)
    qe.evaluate()
    print array(qe.getOutput())

  def test_nl_system(self):
    """
    y'' = a + (y')^2 , y(0)=y0, y'(0)=yc0
    
    The solution is:
    y=(2*y0-log(yc0^2/a+1))/2-log(cos(atan(yc0/sqrt(a))+sqrt(a)*t))

    """
    self.message("Nonlinear ODE sys")
    A=array([1,0.1])
    p0 = 1.13
    y0=A[0]
    yc0=dy0=A[1]
    te=0.4

    t=SX.sym("t")
    q=SX.sym("y",2,1)
    p=SX.sym("p",1,1)
    # y
    # y'
    f=SXFunction("f", daeIn(x=q,p=p,t=t),daeOut(ode=vertcat([q[1],p[0]+q[1]**2 ])))
    opts = {}
    opts["reltol"] = 1e-15
    opts["abstol"] = 1e-15
    #opts["verbose"] = True
    opts["steps_per_checkpoint"] = 10000
    opts["fsens_err_con"] = True
    opts["t0"] = 0
    opts["tf"] = te
    integrator = Integrator("integrator", "cvodes", f, opts)

    t0   = MX(0)
    tend = MX(te)
    q0   = MX.sym("q0",2,1)
    par  = MX.sym("p",1,1)
    qend = integrator({'x0':q0, 'p':par})["xf"]
    qe=MXFunction("qe", [q0,par],[qend])
    qendJ=integrator.jacobian("x0","xf")
    qendJ = qendJ({'x0':q0, 'p':par})['jac']
    qeJ=MXFunction("qeJ", [q0,par],[qendJ])

    qe.setInput(A,0)
    qe.setInput(p0,1)
    qe.evaluate()

    print qe.getOutput()[0]
    print qe.getOutput()[1]
    
    self.assertAlmostEqual(qe.getOutput()[0],(2*y0-log(yc0**2/p0+1))/2-log(cos(arctan(yc0/sqrt(p0))+sqrt(p0)*te)),11,"Nonlin ODE")
    self.assertAlmostEqual(qe.getOutput()[1],sqrt(p0)*tan(arctan(yc0/sqrt(p0))+sqrt(p0)*te),11,"Nonlin ODE")
    
    qeJ.setInput(A,0)
    qeJ.setInput(p0,1)
    qeJ.evaluate()
    
    Jr = array([[1,(sqrt(p0)*tan(sqrt(p0)*te+arctan(dy0/sqrt(p0)))-dy0)/(dy0**2+p0)],[0,(p0*tan(sqrt(p0)*te+arctan(dy0/sqrt(p0)))**2+p0)/(dy0**2+p0)]])
    self.checkarray(qeJ.getOutput(),Jr,"jacobian of Nonlin ODE")
    
    Jf=qe.jacobian(0,0)
    Jf.setInput(A,0)
    Jf.setInput(p0,1)
    Jf.evaluate()
    self.checkarray(Jf.getOutput(),Jr,"Jacobian of Nonlin ODE")
    
    Jf=qe.jacobian(0,0)
    Jf.setInput(A,0)
    Jf.setInput(p0,1)
    Jf.evaluate()
    self.checkarray(Jf.getOutput(),Jr,"Jacobian of Nonlin ODE")
    
    Jr = matrix([[(sqrt(p0)*(te*yc0**2-yc0+p0*te)*tan(arctan(yc0/sqrt(p0))+sqrt(p0)*te)+yc0**2)/(2*p0*yc0**2+2*p0**2)],[(sqrt(p0)*((te*yc0**2-yc0+p0*te)*tan(arctan(yc0/sqrt(p0))+sqrt(p0)*te)**2+te*yc0**2-yc0+p0*te)+(yc0**2+p0)*tan(arctan(yc0/sqrt(p0))+sqrt(p0)*te))/(sqrt(p0)*(2*yc0**2+2*p0))]])  
    
    Jf=qe.jacobian(1,0)
    Jf.setInput(A,0)
    Jf.setInput(p0,1)
    Jf.evaluate()
    self.checkarray(Jf.getOutput(),Jr,"Jacobian of Nonlin ODE")
    Jf=qe.jacobian(1,0)
    Jf.setInput(A,0)
    Jf.setInput(p0,1)
    Jf.evaluate()
    self.checkarray(Jf.getOutput(),Jr,"Jacobian of Nonlin ODE")
    
    qendJ=integrator.jacobian("p","xf")
    qendJ = qendJ({'x0':q0,'p':par})['jac']
    qeJ=MXFunction("qeJ", [q0,par],[qendJ])

    qeJ.setInput(A,0)
    qeJ.setInput(p0,1)
    qeJ.evaluate()
    
    self.checkarray(qeJ.getOutput(),Jr,"jacobian of Nonlin ODE")
    
    
    
    
    qeJf=MXFunction("qeJf", [q0,par],[vec(qeJ.call([q0,par])[0])])
    
    H=qeJf.jacobian(0,0)
    H.setInput(A,0)
    H.setInput(p0,1)
    H.evaluate()
    def sec(x):
      return 1.0/cos(x)
    Hr = array([[0,0],[0,-(2*yc0*tan(arctan(yc0)+te))/(yc0**4+2*yc0**2+1)+sec(arctan(yc0)+te)**2/(yc0**4+2*yc0**2+1)+(2*yc0**2)/(yc0**4+2*yc0**2+1)-1/(yc0**2+1)],[0,0],[0,-(2*yc0*tan(arctan(yc0)+te)**2)/(yc0**4+2*yc0**2+1)+(2*sec(arctan(yc0)+te)**2*tan(arctan(yc0)+te))/(yc0**4+2*yc0**2+1)-(2*yc0)/(yc0**4+2*yc0**2+1)]])
    print array(H.getOutput())
    print Hr
        

  def test_hessian2D(self):
    self.message("hessian")
    N=2

    x0_ = DMatrix([1,0.1])
    A_  = DMatrix([[3,1],[0.74,4]])

    A = SX.sym("A",N,N)
    x = SX.sym("x",N)

    ode = SXFunction("ode", daeIn(x=x, p=vec(A)),daeOut(ode=mul(A,x)))
    I = Integrator("I", "cvodes", ode, {"fsens_err_con": True, 'reltol' : 1e-12})
    I.setInput(x0_,"x0")
    I.setInput(vec(A_),"p")
    I.evaluate()

    q0=MX.sym("q0",N)
    p=MX.sym("p",N*N)
    qe = MXFunction("qe", [q0,p],integratorOut(**I({'x0':q0,'p':p})))

    JT = MXFunction("JT", [q0,p],[qe.jac(1,0).T])

    H  = JT.jacobian(1)
    H.setInput(x0_,0)
    H.setInput(vec(A_),1)
    H.evaluate()

    H1 = H.getOutput()
    
    ## Joel: Only Hessians of scalar functions allowed
    #H = qe.hessian(1)
    #H.setInput(x0_,0)
    #H.setInput(vec(A_),1)
    #H.evaluate()
    #H2 = H.getOutput()
    
    #self.checkarray(H1,H2,"hessian")
    
  def test_issue535(self):
    self.message("regression test for #535")
    t=SX.sym("t")
    x=SX.sym("x")
    rx=SX.sym("rx")
    p=SX.sym("p")
    dp=SX.sym("dp")

    z=SX.sym("z")
    rz=SX.sym("rz")
    rp=SX.sym("rp")
    f = SXFunction("f", daeIn(**{'x': x, 'z': z}),daeOut(**{'alg': x-z, 'ode': z}))
    g = SXFunction("g", rdaeIn(**{'x': x, 'z': z, 'rx': rx, 'rz': rz}),rdaeOut(**{'alg': x-rz, 'ode': rz}))

    integrator = Integrator("integrator", "idas", (f,g), {'calc_ic': True, 'tf': 2.3, 'reltol': 1e-10, 'augmented_options': {'reltol': 1e-09, 'abstol': 1e-09 }, 'calc_icB': True, 'abstol': 1e-10, 't0': 0.2})

    integrator.setInput(7.1,"x0")
    if not integrator.getInput("p").isempty():
      integrator.setInput(2,"p")
    if not integrator.getInput("rx0").isempty():
      integrator.setInput(0.13,"rx0")
    if not integrator.getInput("rp").isempty():
      integrator.setInput(0.127,"rp")

    integrator.evaluate()
    
  def test_collocationPoints(self):
    self.message("collocation points")
    with self.assertRaises(Exception):
      collocationPoints(0,"radau")
    with self.assertRaises(Exception): 
      collocationPoints(10,"radau")
    with self.assertRaises(Exception):
      collocationPoints(0,"legendre")
    with self.assertRaises(Exception): 
      collocationPoints(10,"legendre")
    with self.assertRaises(Exception):
      collocationPoints(1,"foo")
      
    for k in range(1,10):
      r = collocationPoints(k,"radau")
      self.assertEqual(len(r),k+1)
      self.checkarray(DMatrix(r[-1]),DMatrix([1]))
    for k in range(1,10):
      r = collocationPoints(k,"legendre")
      self.assertEqual(len(r),k+1) 
      
if __name__ == '__main__':
    unittest.main()

