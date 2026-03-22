function setup_matlab_paths()
%SETUP_MATLAB_PATHS Add project and YALMIP paths for this workspace.

modelRoot = fileparts(mfilename('fullpath'));
repoRoot = fileparts(modelRoot);

addpath(genpath(modelRoot));

yalmipRoot = fullfile(repoRoot, 'external', 'YALMIP');
if exist(yalmipRoot, 'dir')
    addpath(genpath(yalmipRoot));
end

gurobiRoot = 'C:\gurobi1301\win64';
gurobiMatlab = fullfile(gurobiRoot, 'matlab');
gurobiBin = fullfile(gurobiRoot, 'bin');
gurobiLicense = 'C:\Users\Farkas\gurobi.lic';
if exist(gurobiMatlab, 'dir')
    addpath(gurobiMatlab);
end
if exist(gurobiBin, 'dir')
    setenv('GUROBI_HOME', gurobiRoot);
    setenv('PATH', [getenv('PATH') ';' gurobiBin]);
end
if exist(gurobiLicense, 'file')
    setenv('GRB_LICENSE_FILE', gurobiLicense);
end
end
