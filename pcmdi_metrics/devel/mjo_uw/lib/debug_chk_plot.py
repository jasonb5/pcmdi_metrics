import vcs

def debug_chk_plot():
    x = vcs.init()
    x.plot(d_seg_x_ano)
    x.png('../result/d_seg_x_ano.png')
    x.clear()
    x.plot(Power)
    x.png('../result/power.png')
    x.clear()
    x.plot(OEE)
    x.png('../result/OEE.png')
    x.clear()
    x.plot(OEE_subset)
    x.png('../result/OEE_subset.png')
    x.clear()
    x.plot(segment[year])
    x.png('../result/segment.png')
    x.clear()
    x.plot(daSeaCyc)
    x.png('../result/daSeaCyc.png')
    x.clear()
    x.plot(segment_ano[year])
    x.png('../result/segment_ano.png')
