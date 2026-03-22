function data = load_codex_folder(folderName, modelRoot)
%LOAD_CODEX_FOLDER Lightweight bridge to existing Codex-side project files.

switch lower(strtrim(folderName))
    case 'economic_params'
        data = load_codex_economic_params(fullfile(fileparts(modelRoot), ...
            'RL_capacity_optimization', 'config', 'economic_params.py'));
    case 'market_scenarios'
        data = load_codex_market_scenarios(fullfile(fileparts(modelRoot), ...
            'RL_capacity_optimization', 'config', 'market_scenarios.py'));
    otherwise
        error('Unsupported Codex folder request: %s', folderName);
end
end
