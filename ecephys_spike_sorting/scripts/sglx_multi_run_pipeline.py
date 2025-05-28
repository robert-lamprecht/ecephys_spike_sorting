import os
import sys
import subprocess

from helpers import SpikeGLX_utils
from helpers import log_from_json
from helpers import run_one_probe
from create_input_json import createInputJson


# script to run CatGT, kilosort, postprocessing and TPrime on data collected using
# SpikeGLX. The construction of the paths assumes data was saved with
# "Folder per probe" selected (probes stored in separate folders) AND
# that CatGT is run with the -out_prb_fld option

# -------------------------------
# -------------------------------
# User input -- Edit this section
# -------------------------------
# -------------------------------

# ks_ver  sets up the output tag and threshold values.
# To run a specific MATLAB KS, make sure to set up the kilosort_repository in 
# create_input_json; in the module list, call 'kilosort helper'
# To run KS4, use an anaconda install and call 'ks4_helper'

ks_ver = '4'  # needs to be one of: '2.0', '2.5', '3.0', or '4'
ksTag_dict = {'2.0':'ks2', '2.5':'ks25', '3.0':'ks3', '4':'ks4'}
ks_output_tag = ksTag_dict[ks_ver]

# brain region specific params
# can add a new brain region by adding the key and value for each param
# can add new parameters -- any that are taken by create_input_json --
# by adding a new dictionary with entries for each region and setting the 
# according to the new dictionary in the loop to that created json files.


refPerMS_dict = {'default': 2.0, 'cortex': 2.0, 'medulla': 1.5, 'thalamus': 1.0}

# threhold values appropriate for KS2, KS2.5
ksTh2_dict = {'default':'[10,4]', 'cortex':'[10,4]', 'medulla':'[10,4]', 'thalamus':'[10,4]'}
# threshold values appropriate for KS3.0
ksTh3_dict = {'default':'[9,9]', 'cortex':'[9,9]', 'medulla':'[9,9]', 'thalamus':'[9,9]'}
# threshold values appropriate for KS4.0
ksTh4_dict = {'default':'[8,9]', 'cortex':'[8,9]', 'medulla':'[8,9]', 'thalamus':'[8,9]'}

if ks_ver == '2.0' or ks_ver == '2.5':
    ksTh_dict = ksTh2_dict
elif ks_ver == '3.0':    
    ksTh_dict = ksTh3_dict
elif ks_ver == '4':
    ksTh_dict = ksTh4_dict
else:
    print('unknown version of ks, exiting.')
    sys.exit()

# -----------
# Input data
# -----------
# Name for log file for this pipeline run. Log file will be saved in the
# output destination directory catGT_dest
# If this file exists, new run data is appended to it
logName = 'pipeline_test_log.csv'

# Raw data directory = npx_directory
# run_specs = name, gate, trigger and probes to process
npx_directory = r'C:\Users\RobLamp\Emory\Neurosurgery NAY Research - Documents\Rob\Spinal Shock\Leo_20250514'

# Each run_spec is a list of 4 strings:
#   undecorated run name (no g/t specifier, the run field in CatGT)
#   gate index or range of gate indicies, as a string (e.g. '0')
#   triggers to process/concatenate, as a string e.g. '0,400', '0,0 for a single file
#           can replace first limit with 'start', last with 'end'; 'start,end'
#           will concatenate all trials in the probe folder
#   probes to process, as a string, e.g. '0', '0,3', '0:3'
#   brain regions, list of strings, one per probe, to set region specific params
#           these strings must match a key in the param dictionaries above.

run_specs = [									
						['Leo_20250514', '0,1', '0,0', '0', ['default']]
]

# ------------------
# Output destination
# ------------------
# Set to an existing directory; all output will be written here.
# Output will be in the standard SpikeGLX directory structure:
# run_folder/probe_folder/*.bin
catGT_dest = r'C:\Users\RobLamp\Emory\Neurosurgery NAY Research - Documents\Rob\Spinal Shock\Leo_20250514'

# ------------
# CatGT params
# ------------
run_CatGT = True   # set to False to sort/process previously processed data.


# CAR mode for CatGT. Must be equal to 'None', 'gbldmx', 'gblcar' or 'loccar'
car_mode = 'gblcar'
# inner and outer radii, in um for local comman average reference, if used
loccar_min = 40
loccar_max = 160

# flag to process lf. The depth estimation module assumes lf has been processed.
# if selected, must also include a range for filtering in the catGT_cmd_string
process_lf = False


# CatGT commands for bandpass filtering, artifact correction, and zero filling
# Note 1: directory naming in this script requires -prb_fld and -out_prb_fld
# Note 2: this command line includes specification of edge extraction
# see CatGT readme for details
# these parameters will be used for all runs
catGT_cmd_string = '-prb_fld -out_prb_fld -apfilter=butter,12,300,10000 -lffilter=butter,12,1,500 -gfix=0.4,0.10,0.02 '

ni_present = False
ni_extract_string = '-xa=0,0,0,1,3,500 -xia=0,0,1,3,3,0 -xd=0,0,-1,1,50 -xid=0,0,-1,2,1.7 -xid=0,0,-1,3,5'



# --------------------------
# KS2, KS2.5, KS3 parameters
# --------------------------
# parameters that will be constant for all recordings
# Template ekmplate radius and whitening, which are specified in um, will be 
# translated into sites using the probe geometry.
ks_remDup = 0       # used by KS2, 2.5, 3
ks_saveRez = 1      # used by KS2, 2.5, 3
ks_copy_fproc = 0   # used by 2.5, 3, to save drift corrected binary
ks_templateRadius_um = 163    # used by KS2, 2.5, 3
ks_whiteningRadius_um = 163   # used by KS2, 2,5 2.5, 3
ks_minfr_goodchannels = 0.1   # used by KS2, 2.5, 3; set to 0 for KS2.5 and 3

# -------------------------------
# KS2, KS2.5, KS3, KS4 parameters
# -------------------------------
ks_CAR = 0          # CAR already done in catGT
ks_nblocks = 6      # for KS2.5 KS3, and KS4; 1 for rigid registration in drift correction, 
                    # higher numbers to allow different drift for different 'blocks' of the probe

ks4_binning_depth = 5 # for KS4, depth of binning in um
ks4_batch_size = 30000 * 6 # for KS4, number of samples to process at once
# -------------------------------------------------------
# KS4 specific parameters -- these are the default values
# -------------------------------------------------------
ks4_duplicate_spike_ms = 0.25
ks4_min_template_size_um = 10

# If running KS20_for_preprocessed_data:
# (https://github.com/jenniferColonell/KS20_for_preprocessed_data)
# can skip filtering with the doFilter parameter.
# Useful for speed when data has been filtered with CatGT.
# This parameter is not implemented in standard versions of kilosort.
ks_doFilter = 0


# ----------------------
# C_Waves snr radius, um
# ----------------------
c_Waves_snr_um = 160

# ----------------------
# psth_events parameters
# ----------------------
# extract param string for psth events -- copy the CatGT params used to extract
# events that should be exported with the phy output for PSTH plots
# This funciton now happens in TPrime
# If not using set to an empty string
event_ex_param_str = 'xd=0,0,-1,1,50'

# -----------------
# TPrime parameters
# -----------------
runTPrime = False   # set to False if not using TPrime
sync_period = 1.0   # true for SYNC wave generated by imec basestation
toStream_sync_params = 'imec0' # should be ni, imec<probe index>. or obx<obx index>


# ---------------
# Modules List
# ---------------
# List of modules to run per probe; CatGT and TPrime are called once for each run,
# and should not be included here.
modules = [            
            'ks4_helper',
            'kilosort_postprocessing',
            #'noise_templates',  
            'mean_waveforms',
            'quality_metrics'
			]

json_directory = r'C:\Users\RobLamp\ecephys_spike_sorting\json_files'

# -----------------------
# -----------------------
# End of user input
# -----------------------
# -----------------------

if ks_ver in ['2.0','2.5','3.0'] and 'kilosort_helper' not in modules and 'ks4_helper' in modules:
    print('For MATLAB versions of KS, run kilosort_helper module')
    sys.exit()
if ks_ver == '4' and 'ks4_helper' not in modules and 'kilosort_helper' in modules:
    print('For kilsort 4, run ks4_helper module')
    sys.exit()

# delete the existing CatGT.log
try:
    os.remove('CatGT.log')
except OSError:
    pass

# delete existing Tprime.log
try:
    os.remove('Tprime.log')
except OSError:
    pass

# delete existing C_waves.log
try:
    os.remove('C_Waves.log')
except OSError:
    pass

# check for existence of log file, create if not there
logFullPath = os.path.join(catGT_dest, logName)
if not os.path.isfile(logFullPath):
    # create the log file, write header
    log_from_json.writeHeader(logFullPath)
    
    


for spec in run_specs:

    session_id = spec[0]

    
    # Make list of probes from the probe string
    prb_list = SpikeGLX_utils.ParseProbeStr(spec[3])
    
    [first_gate, last_gate] = SpikeGLX_utils.ParseGateStr(spec[1])
    run_folder_name = spec[0] + '_g' + repr(first_gate)
    prb0_fld_name = run_folder_name + '_imec' + prb_list[0]
    prb0_fld = os.path.join(npx_directory, run_folder_name, prb0_fld_name)
    first_trig, last_trig = SpikeGLX_utils.ParseTrigStr(spec[2], prb_list[0], str(first_gate), prb0_fld)
    
    if last_gate > first_gate:
        # loop over other gates to check ranges of triggers 
        # If your gates have varying numbers of triggers, make sure to set
        # 't_miss_ok' in the catGT_cmd_string above
        for gate_index in range(first_gate + 1, last_gate+1):
            # build path to the first probe folder for each gate; look into that folder
            # to determine the range of trials if the user specified t limits as
            # start and end
            run_folder_name = spec[0] + '_g' + repr(first_gate)
            prb0_fld_name = run_folder_name + '_imec' + prb_list[0]
            prb0_fld = os.path.join(npx_directory, run_folder_name, prb0_fld_name)
            curr_first, curr_last = SpikeGLX_utils.ParseTrigStr(spec[2], prb_list[0], str(gate_index), prb0_fld)
            if curr_first < first_trig:
                first_trig = curr_first
            if curr_last > last_trig:
                last_trig = curr_last
    
    
    trigger_str = repr(first_trig) + ',' + repr(last_trig)
    
    # loop over all probes to build json files of input parameters
    # initalize lists for input and output json files
    catGT_input_json = []
    catGT_output_json = []
    module_input_json = []
    module_output_json = []
    session_id = []
    data_directory = []
    
    # first loop over probes creates json files containing parameters for
    # both preprocessing (CatGt) and sorting + postprocessing
    
    for i, prb in enumerate(prb_list):
            
        
        print('Creating json file for CatGT on probe: ' + prb)
        #create CatGT command for this probe
        catGT_input_json.append(os.path.join(json_directory, spec[0] + prb + '_CatGT' + '-input.json'))
        catGT_output_json.append(os.path.join(json_directory, spec[0] + prb + '_CatGT' + '-output.json'))
        
        # build extract string for SYNC channel for this probe
        # sync_extract = '-SY=' + prb +',-1,6,500'
        
        # if this is the first probe proceessed, process the ni stream with it
        if i == 0 and ni_present:
            catGT_stream_string = '-ap -ni'
            extract_string = ni_extract_string
        else:
            catGT_stream_string = '-ap'
            extract_string = ''
            
        if process_lf:
            catGT_stream_string = catGT_stream_string + ' -lf'
        
        # build name of first trial to be concatenated/processed;
        # allows reading of the metadata
        run_str = spec[0] + '_g' + str(first_gate) 
        run_folder = run_str
        prb_folder = run_str + '_imec' + prb
        input_data_directory = os.path.join(npx_directory, run_folder, prb_folder)
        fileName = run_str + '_t' + repr(first_trig) + '.imec' + prb + '.ap.bin'
        continuous_file = os.path.join(input_data_directory, fileName)
        metaName = run_str + '_t' + repr(first_trig) + '.imec' + prb + '.ap.meta'
        input_meta_fullpath = os.path.join(input_data_directory, metaName)
        
        print(input_meta_fullpath)
         
        info = createInputJson(catGT_input_json[i], npx_directory=npx_directory, 
                                       continuous_file = continuous_file,
                                       kilosort_output_directory=catGT_dest,
                                       input_meta_path = input_meta_fullpath,
                                       catGT_run_name = spec[0],
                                       gate_string = spec[1],
                                       trigger_string = trigger_str,
                                       probe_string = prb,
                                       catGT_stream_string = catGT_stream_string,
                                       catGT_car_mode = car_mode,
                                       catGT_loccar_min_um = loccar_min,
                                       catGT_loccar_max_um = loccar_max,
                                       catGT_cmd_string = catGT_cmd_string + ' ' + extract_string,                                       
                                       extracted_data_directory = catGT_dest
                                       )      
        
        
        #create json files for the other modules
        print('Creating json file for sorting on probe: ' + prb) 
        session_id.append(spec[0] + '_imec' + prb)
        
        module_input_json.append(os.path.join(json_directory, session_id[i] + '-input.json'))
            
        # location of the binary created by CatGT, using -out_prb_fld
        run_str = spec[0] + '_g' + str(first_gate)
        run_folder = 'catgt_' + run_str
        prb_folder = run_str + '_imec' + prb
        data_directory.append(os.path.join(catGT_dest, run_folder, prb_folder))
        fileName = run_str + '_tcat.imec' + prb + '.ap.bin'
        continuous_file = os.path.join(data_directory[i], fileName)
 
        outputName = 'imec' + prb + '_' + ks_output_tag

        # kilosort_postprocessing and noise_templates moduules alter the files
        # that are input to phy. If using these modules, keep a copy of the
        # original phy output
        if ('kilosort_postprocessing' in modules) or('noise_templates' in modules):
            ks_make_copy = True
        else:
            ks_make_copy = False

        kilosort_output_dir = os.path.join(data_directory[i], outputName)

        print(data_directory[i])
        print(continuous_file)
        
        # get region specific parameters
        ks_Th = ksTh_dict.get(spec[4][i])
        refPerMS = refPerMS_dict.get(spec[4][i])
        print( 'ks_Th: ' + repr(ks_Th) + ' ,refPerMS: ' + repr(refPerMS))

        info = createInputJson(module_input_json[i], npx_directory=npx_directory, 
	                                   continuous_file = continuous_file,
                                       input_meta_path = input_meta_fullpath,
									   kilosort_output_directory=kilosort_output_dir,
                                       ks_make_copy = ks_make_copy,
                                       noise_template_use_rf = False,
                                       catGT_run_name = session_id[i],
                                       gate_string = spec[1],
                                       probe_string = spec[3],
                                       ks_ver = ks_ver,
                                       ks_remDup = ks_remDup,                   
                                       ks_finalSplits = 1,
                                       ks_labelGood = 1,
                                       ks_saveRez = ks_saveRez,
                                       ks_copy_fproc = ks_copy_fproc,
                                       ks_helper_noise_threshold = 20,
                                       ks_minfr_goodchannels = ks_minfr_goodchannels,                  
                                       ks_whiteningRadius_um = ks_whiteningRadius_um,
                                       ks_doFilter = ks_doFilter,
                                       ks_Th = ks_Th,
                                       ks_CSBseed = 1,
                                       ks_LTseed = 1,
                                       ks_templateRadius_um = ks_templateRadius_um,
                                       ks_nblocks = ks_nblocks,
                                       ks_CAR = ks_CAR,
                                       extracted_data_directory = data_directory[i],
                                       event_ex_param_str = event_ex_param_str,
                                       c_Waves_snr_um = c_Waves_snr_um,
                                       c_Waves_calc_half = False,
                                       qm_isi_thresh = refPerMS/1000,
                                       ks4_duplicate_spike_ms = ks4_duplicate_spike_ms,
                                       ks4_min_template_size_um = ks4_min_template_size_um,
                                       ks4_binning_depth = ks4_binning_depth,
                                       ks4_batch_size = ks4_batch_size,
                                       include_pc_metrics = True
                                       )   

        # copy json file to data directory as record of the input parameters 
       
        
    # loop over probes for processing.    
    for i, prb in enumerate(prb_list):  
        
        run_one_probe.runOne( session_id[i],
                 json_directory,
                 data_directory[i],
                 run_CatGT,
                 catGT_input_json[i],
                 catGT_output_json[i],
                 modules,
                 module_input_json[i],
                 logFullPath )
                
        
      
    if runTPrime:
               
        # after loop over probes, run TPrime to create files of 
        # event times -- edges detected in auxialliary files and spike times 
        # from each probe -- all aligned to a reference stream.
        
        # Uncomment line belwo to create a set of all ni time points, which can be
        # corrected by TPrime. This output is used to obtain analog values
        # from the NI stream at spike times.
        # Will cause an error if no ni stream exists.
        # SpikeGLX_utils.CreateNITimeEvents(spec[0], spec[1], catGT_dest)
    
        # create json files for calling TPrime
        session_id = spec[0] + '_TPrime'
        input_json = os.path.join(json_directory, session_id + '-input.json')
        output_json = os.path.join(json_directory, session_id + '-output.json')                      
        
        info = createInputJson(input_json, npx_directory=npx_directory, 
    	                                   continuous_file = continuous_file,
                                           input_meta_path = input_meta_fullpath,
                                           catGT_run_name = spec[0],
                                           gate_string = spec[1],
    									   kilosort_output_directory=kilosort_output_dir,
                                           extracted_data_directory = catGT_dest,                                           
                                           tPrime_ni_ex_list = ni_extract_string,
                                           event_ex_param_str = event_ex_param_str,
                                           sync_period = 1.0,
                                           toStream_sync_params = toStream_sync_params,
                                           ks_output_tag = ks_output_tag
                                           ) 
        
        command = sys.executable + " -W ignore -m ecephys_spike_sorting.modules." + 'tPrime_helper' + " --input_json " + input_json \
    		          + " --output_json " + output_json
        subprocess.check_call(command.split(' '))  
        
        

