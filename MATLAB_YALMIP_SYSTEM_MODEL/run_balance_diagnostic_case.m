function out = run_balance_diagnostic_case()
%RUN_BALANCE_DIAGNOSTIC_CASE Positive-production reference case for balance checks.

setup_matlab_paths;
modelRoot = fileparts(mfilename('fullpath'));
p = default_model_params(modelRoot);

% Use a positive-production reference case so balance checks are informative.
p.model.horizon_steps = 168;
p.model.allow_grid = false;
p.solver.verbose = 0;
p.storage.enforce_cyclic_terminal = false;
p.battery.enforce_cyclic_terminal = false;

results = run_system_optimization(p);
report = analyze_balances(results, p);

out = struct();
out.params = p;
out.results = results;
out.report = report;

disp('Balance diagnostic summary:');
disp(report);
end
