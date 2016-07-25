import sys, os
import string
import subprocess
import cdms2 as cdms
import cdutil
import cdtime
import genutil
import time
import json
from eofs.cdms import Eof
import vcs
import numpy as NP

libfiles = ['durolib.py',
            'get_pcmdi_data.py',
            'eof_analysis.py',
            'write_nc_output.py',
            'plot_map.py']

for lib in libfiles:
  #execfile(os.path.join('../lib/',lib))
  execfile(os.path.join('../../lib/',lib))

mip = 'cmip5'
#exp = 'piControl'
exp = 'historical'
model = 'ACCESS1-0'
fq = 'mo'
realm = 'atm'
run = 'r1i1p1'

test = True
#test = False

mode = 'pdo' # Pacific Decadal Oscillation

obs_compare = True
#obs_compare = False

nc_out = True
#nc_out = False

plot = True
#plot = False

if test:
  models = ['ACCESS1-0']  # Test just one model
  #models = ['ACCESS1-3']  # Test just one model
  seasons = ['DJF']
  #seasons = ['MAM']
else:
  models = get_all_mip_mods(mip,exp,fq,realm,var)
  seasons = ['DJF','MAM','JJA','SON']

syear = 1900
#syear = 1990 # To match with ERAINT...
eyear = 2005

start_time = cdtime.comptime(syear,1,1)
end_time = cdtime.comptime(eyear,12,31)

if mode == 'pdo':
  var = 'ts'
  lat1 = 20
  lat2 = 70
  lon1 = 110
  lon2 = 260

# Unit adjustment
if var == 'psl':
  unit_adj = 0.01 # Pa to hPa
else:
  unit_adj = 1.

#=================================================
# Observation
#-------------------------------------------------
if obs_compare:
  #obs_path = '/clim_obs/obs/atm/mo/'+var+'/ERAINT/'+var+'_ERAINT_198901-200911.nc' # ts_ERAINT is already masked out, only SST, while model ts includes land area
  obs_path = '/clim_obs/obs/ocn/mo/tos/UKMETOFFICE-HadISST-v1-1/130122_HadISST_sst.nc'
  fo = cdms.open(obs_path)
  #obs_timeseries = fo(var,latitude=(lat1,lat2),longitude=(lon1,lon2),time=(start_time,end_time))*unit_adj 
  obs_timeseries = fo('sst',latitude=(lat1,lat2),longitude=(lon1,lon2),time=(start_time,end_time))*unit_adj 
  cdutil.setTimeBoundsMonthly(obs_timeseries)

  # reomove annual cycle
  obs_timeseries = cdutil.ANNUALCYCLE.departures(obs_timeseries)

  ref_grid = obs_timeseries.getGrid() # Extract grid information for Regrid below

  eof1_obs={}
  pc1_obs={}
  frac1_obs={}
  
  #-------------------------------------------------
  # EOF analysis
  #- - - - - - - - - - - - - - - - - - - - - - - - -
  eof1_obs, pc1_obs, frac1_obs = eof_analysis_get_first_variance_mode(obs_timeseries)

  #-------------------------------------------------
  # Record results
  #- - - - - - - - - - - - - - - - - - - - - - - - -
  # Set output file name for both NetCDF and plot ---
  output_file_name_obs = mode+'_'+var+'_eof1_obs_'+str(syear)+'-'+str(eyear)

  # Save in NetCDF output ---
  if nc_out:
    write_nc_output(output_file_name_obs, eof1_obs, pc1_obs, frac1_obs)

  # Plot map --- 
  if plot:
    #plot_map(mode, 'obs', syear, eyear, '', eof1_obs, frac1_obs, output_file_name_obs)
    plot_map(mode, 'obs (HadISST)', syear, eyear, '', eof1_obs, frac1_obs, output_file_name_obs)

#=================================================
# Model
#-------------------------------------------------
var_mode_stat_dic={}
var_mode_stat_dic['RESULTS']={}

for model in models:
  var_mode_stat_dic['RESULTS'][model]={}
  var_mode_stat_dic['RESULTS'][model]['defaultReference']={}
  var_mode_stat_dic['RESULTS'][model]['defaultReference'][mode]={}

  model_path = get_latest_pcmdi_mip_data_path(mip,exp,model,fq,realm,var,run)
  #model_path = '/work/cmip5/historical/atm/mo/psl/cmip5.'+model+'.historical.r1i1p1.mo.atm.Amon.psl.ver-1.latestX.xml'
  print model_path
  print model

  f = cdms.open(model_path)
  #model_timeseries = f(var,latitude=(lat1,lat2),longitude=(lon1,lon2),time=(start_time,end_time))*unit_adj
  model_timeseries = f(var,time=(start_time,end_time))*unit_adj
  cdutil.setTimeBoundsMonthly(model_timeseries)

  # Remove annual cycle
  model_timeseries = cdutil.ANNUALCYCLE.departures(model_timeseries)

  #-------------------------------------------------
  # Mask out: extract SST only..
  #- - - - - - - - - - - - - - - - - - - - - - - - -
  if mode == 'pdo':
    # model land fraction
    #model_lf_path = '/work/cmip5/fx/fx/sftlf/cmip5.'+model+'.historical.r0i0p0.fx.atm.fx.sftlf.ver-1.latestX.xml'
    model_lf_path = '/work/cmip5/fx/fx/sftlf/cmip5.ACCESS1-0.historical.r0i0p0.fx.atm.fx.sftlf.ver-1.latestX.xml'
    print model_lf_path
    
    f_lf = cdms.open(model_lf_path)
    #lf = f_lf('sftlf',latitude=(lat1,lat2),longitude=(lon1,lon2))
    lf = f_lf('sftlf')

    model_timeseries,lf_timeConst = genutil.grower(model_timeseries,lf) # Matching dimension

    #opt1 = True
    opt1 = False

    if opt1:
      model_timeseries_masked = NP.ma.masked_where(lf_time>0, model_timeseries) # mask out land (include only 100% ocean grid)
    else: 
      lf2 = (100.-lf)/100.
      model_timeseries,lf2_timeConst = genutil.grower(model_timeseries,lf2) # Matching dimension
      model_timeseries_masked = model_timeseries * lf2_timeConst # mask out land considering fraction

    time = model_timeseries.getTime()
    model_timeseries_masked.setAxis(0,time)

    lat = model_timeseries.getLatitude()
    model_timeseries_masked.setAxis(1,lat)

    lon = model_timeseries.getLongitude()
    model_timeseries_masked.setAxis(2,lon)

    model_timeseries = model_timeseries_masked

  #-------------------------------------------------
  # Get SST anomaly
  # Monthly index timeseries defined as the leading principal component (PC) of North Pacific (20:70N, 110E:100W) area-weighted SST* anomalies, where SST* denotes that the global mean SST has been removed at each timestep. Pattern created by regressing global SST anomalies onto normalized PC timeseries. Low pass-filtered timeseries (black curve) is based on a a 61-month running mean. 
  #- - - - - - - - - - - - - - - - - - - - - - - - -

  model_timeseries_subDomain = model_timeseries(latitude=(lat1,lat2),longitude=(lon1,lon2))

  #opt2 = True
  opt2 = False

  if opt2:
    #model_global_mean_timeseries = cdutil.averager(model_timeseries, axis='xy', weights='weighted')
    model_global_mean_timeseries = cdutil.averager(model_timeseries(latitude=(-60,70)), axis='xy', weights='weighted')

    model_timeseries_subDomain, model_global_mean_timeseries = genutil.grower(model_timeseries_subDomain, model_global_mean_timeseries) # Matching dimension
    model_timeseries_subDomain_anom = model_timeseries_subDomain - model_global_mean_timeseries 
  else:
    model_timeseries_subDomain_anom = cdutil.ANNUALCYCLE.departures(model_timeseries_subDomain)

  #-------------------------------------------------
  # EOF analysis
  #- - - - - - - - - - - - - - - - - - - - - - - - -
  eof1, pc1, frac1 = eof_analysis_get_first_variance_mode(model_timeseries_subDomain_anom)

  if not opt1:
    eof1 = eof1 / lf2(latitude=(lat1,lat2),longitude=(lon1,lon2))

  #-------------------------------------------------
  # Record results
  #- - - - - - - - - - - - - - - - - - - - - - - - -
  # Set output file name for both NetCDF and plot ---
  output_file_name = mode+'_psl_eof1_'+model+'_'+str(syear)+'-'+str(eyear)

  # Save in NetCDF output ---
  if nc_out:
    write_nc_output(output_file_name,eof1,pc1,frac1)
    
  # Plot map --- 
  if plot:
    #plot_map(mode, model, syear, eyear, season, eof1, frac1, output_file_name)
    plot_map(mode, model, syear, eyear, '', eof1, frac1, output_file_name)

  #-------------------------------------------------
  # OBS statistics (regrid will be needed) output, save as dictionary
  #- - - - - - - - - - - - - - - - - - - - - - - - -
  if obs_compare:

    # Regrid (interpolation, model grid to ref grid) ---
    eof1_regrid = eof1.regrid(ref_grid,regredTool='regrid2') # regrid location test 1

    # RMS difference ---
    rms = genutil.statistics.rms(eof1_regrid, eof1_obs, axis='xy')

    # Spatial correlation weighted by area ('generate' option for weights) ---
    cor = genutil.statistics.correlation(eof1_regrid, eof1_obs, weights='generate', axis='xy')

    # Add to dictionary for json output ---
    var_mode_stat_dic['RESULTS'][model]['defaultReference'][mode]['rms'] = float(rms)
    var_mode_stat_dic['RESULTS'][model]['defaultReference'][mode]['cor'] = float(cor)
    var_mode_stat_dic['RESULTS'][model]['defaultReference'][mode]['frac'] = float(frac1)

#=================================================
# OBS statistics -- Write dictionary to json file
#-------------------------------------------------
if obs_compare:
  json_filename = 'var_mode_'+mode+'_eof1_stat_' + mip + '_' + exp + '_' + run + '_' + fq + '_' + realm + '_' + str(syear) + '-' + str(eyear)
  json.dump(var_mode_stat_dic, open(json_filename + '.json','w'),sort_keys=True, indent=4, separators=(',', ': '))
