#!/usr/bin/env python

import shutil
import json
import subprocess
import os
import time

import atomsci.ddm.pipeline.parameter_parser as parse
import atomsci.ddm.pipeline.compare_models as cm
from atomsci.ddm.utils import llnl_utils

def clean():
    """
    Clean test files
    """
    if "hyperparam_search" in os.listdir():
        shutil.rmtree("hyperparam_search")

    if "logs" in os.listdir():
        shutil.rmtree("logs")

    if "run.sh" in os.listdir():
        os.remove("run.sh")

    if "slurm_files" in os.listdir():
        shutil.rmtree("slurm_files")

def wait_to_finish(json_file, max_time=600):
    """ Run hyperparam search and return pref_df

    Given parased parameter namespace build the hyperparam search command and
    wait for training to complete. Once training is complete, retrun the perf_df.
    This function repeatedly calls get_filesystem_perf_results until it sees
    at least the number of jobs generated by pparams.

    Args:
        json_file (str): Path to json_file to run.

        max_type (int): Max wait time in seconds. Default 600. -1 is unlimited
            wait time.

    Returns:
        DataFrame or None: returns perf_df if training completes in time. 

    """
    with open(json_file, "r") as f:
        hp_params = json.load(f)

    pparams = parse.wrapper(hp_params)

    script_dir = pparams.script_dir
    python_path = pparams.python_path
    result_dir = pparams.result_dir
    pred_type = pparams.prediction_type

    run_cmd = f"{python_path} {script_dir}/utils/hyperparam_search_wrapper.py --config_file {json_file}"
#    os.system(run_cmd)
    p = subprocess.Popen(run_cmd.split(' '), stdout=subprocess.PIPE)
    out = p.stdout.read().decode("utf-8")

    num_jobs = out.count('Submitted batch job')
    num_found = 0
    time_waited = 0
    wait_interval = 30

    print("Waiting %d jobs to finish. Checks every 30 seconds" % num_jobs)
    while (num_found < num_jobs) and ((max_time == -1) or (time_waited < max_time)):
        # wait until the training jobs have finished
        time.sleep(wait_interval) # check for results every 30 seconds
        time_waited += wait_interval
        try:
            result_df = cm.get_filesystem_perf_results(result_dir, pred_type=pred_type)
            num_found = result_df.shape[0]
        except:
            num_found = 0
            result_df = None

    return result_df

def test():
    """
    Test full model pipeline: Curate data, fit model, and predict property for new compounds
    """

    # Clean
    # -----
    clean()

    # Run ECFP NN hyperparam search
    # ------------
    if llnl_utils.is_lc_system():
        result_df = wait_to_finish("nn_ecfp.json", max_time=-1)
        assert not result_df is None # Timed out
        if 'test_r2_score' in result_df.columns:
            assert max(result_df['test_r2_score'].values) > 0.6 # should do at least this well. I saw values like 0.687
        if 'best_test_r2_score' in result_df.columns:
            assert max(result_df['best_test_r2_score'].values) > 0.6 # should do at least this well. I saw values like 0.687
    else:
        assert True

    # Clean
    # -----
    clean()

    if llnl_utils.is_lc_system():
        # Run graphconv NN hyperparam search
        result_df = wait_to_finish("nn_graphconv.json", max_time=-1)
        assert not result_df is None # Timed out
        if 'test_r2_score' in result_df.columns:
            assert max(result_df['test_r2_score'].values) > 0.6 # should do at least this well. I saw values like 0.62
    else:
        assert True
    # Clean
    # -----
    clean()

if __name__ == '__main__':
    test()
