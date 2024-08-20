#!/usr/bin/env python

import shutil
import json
import subprocess
import os
import time

import atomsci.ddm.pipeline.parameter_parser as parse
import atomsci.ddm.pipeline.compare_models as cm
import glob
from atomsci.ddm.utils import llnl_utils

def clean():
    """Clean test files"""
    if "hyperparam_search" in os.listdir():
        shutil.rmtree("hyperparam_search")

    if "logs" in os.listdir():
        shutil.rmtree("logs")

    if "run.sh" in os.listdir():
        os.remove("run.sh")

    if "slurm_files" in os.listdir():
        shutil.rmtree("slurm_files")

    maestro_folders = glob.glob('Test_Maestro_*')
    for mf in maestro_folders:
        shutil.rmtree(mf)

def run_command(command):
    """Runs the command and returns string

    Args:
        command (list): list of strings e.g. ['wc', '-l']

    Returns:
        str: output of the command
    """
    p = subprocess.Popen(command, stdout=subprocess.PIPE)
    out = p.stdout.read().decode("utf-8")

    return out

def wait_to_finish(maestro_run_command, max_time=600):
    """Run hyperparam search and return pref_df

        Given parased parameter namespace build the hyperparam search command and
        wait for training to complete. Once training is complete, retrun the perf_df.
        This function repeatedly calls get_filesystem_perf_results until it sees
        at least the number of jobs generated by pparams.

        Args:
       maestro_run_command (str): Command to start maestro run.

       max_type (int): Max wait time in seconds. Default 600. -1 is unlimited
           wait time.

        Returns:
       bool: Returns True on completetion.

    """
    out = run_command(maestro_run_command.split(' '))

    maestro_folders = glob.glob('Test_Maestro*')
    # We assert here that there should only be one maestro folder.
    # something is wrong with the test otherwise
    assert len(maestro_folders) == 1
    maestro_folder = maestro_folders[0]

    print('folder created')

    # make sure that there's a status file
    status_file = os.path.join(maestro_folder, 'status.csv')
    
    # wait for the file to be available
    while not os.path.exists(status_file):
        time.sleep(2)

    assert os.path.exists(status_file)

    print('status found')

    # check how many jobs got started
    out = run_command(['wc', '-l', status_file])
    num_jobs = int(out.split(' ')[0]) # out expected to look like "2 Test_Maestro..."

    num_completed = 0
    time_waited = 0
    wait_interval = 30
    print("Waiting %d jobs to finish. Checks every 30 seconds" % num_jobs)
    while (num_completed < num_jobs) and ((max_time == -1) or (time_waited < max_time)):
        # wait until the training jobs have finished
        time.sleep(wait_interval) # check for results every 30 seconds
        time_waited += wait_interval
        finished_grep = run_command(['grep', '-c', 'FINISHED', status_file])
        try:
            num_completed = int(finished_grep)
        except ValueError:
            num_completed = 0

        failed_grep = run_command(['grep', '-c', 'FAILED', status_file])
        try:
            num_failed = int(failed_grep)
        except ValueError:
            num_failed = 0

        print(f'{num_completed} jobs finished {num_failed} jobs failed')
        assert num_failed == 0

    # see if you timed out
    assert time_waited < max_time

    return True

def test():
    """Test full model pipeline: Curate data, fit model, and predict property for new compounds"""

    # Clean
    # -----
    clean()

    if not llnl_utils.is_lc_system():
        assert True
        return
        
    # Run ECFP NN hyperparam search
    # ------------
    json_file = "nn_ecfp.json"
    with open(json_file, "r") as f:
        hp_params = json.load(f)
    pparams = parse.wrapper(hp_params)

    print('launch maestro')
    _ = wait_to_finish(f"maestro run -y -p custom_gen.py run_nn_ecfp.yaml", max_time=2*60*60) # wait 2 hours.

    result_df = cm.get_filesystem_perf_results(pparams.result_dir, pparams.prediction_type)
    assert not result_df is None # Timed out
    assert max(result_df.loc[:,result_df.columns.str.contains("test_r2_score")].values) > 0.6 # should do at least this well. I saw values like 0.687
    
    print('waiting for maestro to finish')
    time.sleep(60)

    # Clean
    # -----
    clean()

if __name__ == '__main__':
    test()