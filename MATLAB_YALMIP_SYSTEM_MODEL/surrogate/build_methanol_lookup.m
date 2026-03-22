function lookup = build_methanol_lookup(excelPath, fixedRatio, ratioTolerance, nBreakpoints)
%BUILD_METHANOL_LOOKUP Build a 1D methanol lookup from the Excel dataset.

if ~isfile(excelPath)
    error('Methanol Excel file not found: %s', excelPath);
end

tbl = readtable(excelPath);

required = {'Feed_CO2_mol_s', 'Feed_Ratio_H2_CO2', ...
    'Methanol_Production_kg_h', 'Total_COMP_Power_kW'};
for i = 1:numel(required)
    if ~ismember(required{i}, tbl.Properties.VariableNames)
        error('Missing methanol column: %s', required{i});
    end
end

ratioDistance = abs(tbl.Feed_Ratio_H2_CO2 - fixedRatio);
idx = ratioDistance <= ratioTolerance;

if nnz(idx) < 8
    [~, order] = sort(ratioDistance, 'ascend');
    keepN = min(max(24, nBreakpoints * 2), height(tbl));
    idx = false(height(tbl), 1);
    idx(order(1:keepN)) = true;
end

sub = tbl(idx, :);
if isempty(sub)
    error('No methanol data points were available for surrogate lookup construction.');
end

feedRounded = round(sub.Feed_CO2_mol_s * 1e6) / 1e6;
[G, feedValues] = findgroups(feedRounded);

methanolMean = splitapply(@mean, sub.Methanol_Production_kg_h, G);
powerMean = splitapply(@mean, sub.Total_COMP_Power_kW, G);

[feedValues, order] = sort(feedValues, 'ascend');
methanolMean = methanolMean(order);
powerMean = powerMean(order);

if feedValues(1) > 0
    feedValues = [0; feedValues];
    methanolMean = [0; methanolMean];
    powerMean = [0; powerMean];
end

if numel(feedValues) > nBreakpoints
    sampleFeed = linspace(min(feedValues), max(feedValues), nBreakpoints).';
    sampleMethanol = interp1(feedValues, methanolMean, sampleFeed, 'linear', 'extrap');
    samplePower = interp1(feedValues, powerMean, sampleFeed, 'linear', 'extrap');
else
    sampleFeed = feedValues;
    sampleMethanol = methanolMean;
    samplePower = powerMean;
end

sampleMethanol = max(0.0, sampleMethanol);
samplePower = max(0.0, samplePower);

lookup = struct();
lookup.feed_breakpoints = sampleFeed(:).';
lookup.methanol_breakpoints = sampleMethanol(:).';
lookup.power_breakpoints = samplePower(:).';
lookup.fixed_ratio = fixedRatio;
lookup.feed_min = min(sampleFeed);
lookup.feed_max = max(sampleFeed);
lookup.meta = struct();
lookup.meta.source_excel = excelPath;
lookup.meta.fixed_ratio = fixedRatio;
lookup.meta.ratio_tolerance = ratioTolerance;
lookup.meta.raw_points = height(sub);
lookup.meta.breakpoint_count = numel(sampleFeed);
end
