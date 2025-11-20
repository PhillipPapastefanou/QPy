
mutable struct QPlotSettings

    verbose::Bool

    nrows_per_page::Int
    ncols_per_page::Int

    width_px::Int
    height_px::Int
end

function QPlotSettings()
    
    QPlotSettings( 
    false,
        4, 
        2, 
        600,
        800   
    )
   
end