function [Constraints, aux] = add_pem_constraints(Constraints, vars, params)
%ADD_PEM_CONSTRAINTS Linear PEM production baseline.

Constraints = [Constraints, vars.P_PEM >= 0, vars.m_H2_prod >= 0];
Constraints = [Constraints, vars.P_PEM <= params.pem.max_load * vars.C_PEM];
Constraints = [Constraints, vars.m_H2_prod == params.pem.h2_prod_mol_s_per_kw * vars.P_PEM];

aux = struct();
aux.h2_prod_mol_s_per_kw = params.pem.h2_prod_mol_s_per_kw;
aux.max_load = params.pem.max_load;
end
