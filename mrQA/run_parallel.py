import warnings
from pathlib import Path
from MRdataset.utils import random_name
from MRdataset.config import CACHE_DIR
from mrQA.run_subset import read_subset, merge_subset, merge_from_disk

from mrQA.utils import split_index, create_index, save2pickle, list2txt
import subprocess
import pickle


def parallel_dataset(data_root=None,
                     style='dicom',
                     name=None,
                     reindex=False,
                     include_phantom=False,
                     verbose=False,
                     metadata_root=None,
                     include_nifti_header=False,
                     workers=None,
                     submit_job=False):
    if style != 'dicom':
        raise NotImplementedError(f'Expects dicom, Got {style}')

    if not Path(data_root).is_dir():
        raise OSError('Expected valid directory for --data_root argument,'
                      ' Got {0}'.format(data_root))
    data_root = Path(data_root).resolve()

    if not metadata_root:
        metadata_root = Path.home() / CACHE_DIR
        metadata_root.mkdir(exist_ok=True)

    if not Path(metadata_root).is_dir():
        raise OSError('Expected valid directory for --metadata_root argument,'
                      ' Got {0}'.format(metadata_root))
    metadata_root = Path(metadata_root).resolve()

    if name is None:
        warnings.warn(
            'Expected a unique identifier for caching data. Got NoneType. '
            'Using a random name. Use --name flag for persistent metadata',
            stacklevel=2)
        name = random_name()

    num_sets = create_index(data_root, metadata_root, name, reindex)

    for i in range(num_sets):
        # create slurm script to call run_subset.py
        s_folderpath = metadata_root/f'scripts_{name}'
        s_folderpath.mkdir(parents=True, exist_ok=True)
        s_filename = s_folderpath/f's_{name}_{i}.sh'
        create_slurm_script(s_filename, name, i, 'mrcheck')
        # submit job or run with bash
        if not submit_job:
            subprocess.call(['bash', s_filename])
        else:
            subprocess.call(['sbatch', s_filename])
    complete_dataset = merge_from_disk(metadata_root, name)
    with open(metadata_root/f'{name}.pickle', "wb") as f:
        pickle.dump(complete_dataset.__dict__, f)
    return


def create_slurm_script(filename, dataset_name, seq_no, env='mrqa'):
    with open(filename, 'w') as fp:
        fp.writelines("\n".join([
            '#!/bin/bash',
            '#SBATCH -A med220005p',
            '#SBATCH -N 1',
            '#SBATCH -p RM-shared',
            '#SBATCH --time=01:05:00',
            '#SBATCH --ntasks-per-node=1',
            f'#SBATCH --error={dataset_name}.master{seq_no}.%J.err',
            f'#SBATCH --output={dataset_name}.master{seq_no}.%J.out',

            '#Clear the environment from any previously loaded modules',
            '#module purge > /dev/null 2>&1',

            'source ${HOME}/.bashrc',
            'conda init bash'
            f'conda activate {env}',
            f'mrpc_subset  -i {seq_no} --style dicom --name {dataset_name} &',
            'wait',
            'date',
            'echo - e Download_completed',
            ])
        )


if __name__ == '__main__':
    parallel_dataset(data_root='/media/sinhah/extremessd/ABCD-375/dicom-baseline',
                     name='abcd-375',
                     reindex=True)