from pathlib import Path
from typing import Union

from MRdataset.base import Project
from MRdataset.utils import param_difference, is_hashable

from mrQA.formatter import HtmlFormatter
from mrQA.utils import timestamp, majority_attribute_values, \
    extract_reasons


def check_compliance(dataset: Project,
                     strategy: str = 'majority',
                     output_dir: Union[Path, str] = None,
                     reference_path: Union[Path, str] = None) -> Project:
    """
    Checks mrQA
    @param dataset
    @param output_dir
    @param strategy
    @param reference_path
    """
    if strategy == 'majority':
        dataset = compare_with_majority(dataset)
    else:
        raise NotImplementedError
    generate_report(dataset, output_dir)

    return dataset


def compare_with_majority(dataset: "Project") -> Project:
    """
    Method for post-acquisition compliance. Infers the reference protocol/values
    by looking for the most frequent values, and then identifying deviations

    Parameters
    ----------
    dataset : Project
        MRdataset.base.Project instance for the dataset which is to be checked
        for compliance

    Returns
    -------
    dataset : Project
        Adds the non-compliance information to the same Project instance and
        returns it.
    """
    for modality in dataset.modalities:
        # Calculate reference for comparing
        run_by_echo = dict()
        for subject in modality.subjects:
            for session in subject.sessions:
                for run in session.runs:
                    # Use defaultdict instead?
                    if run.echo_time not in run_by_echo.keys():
                        run_by_echo[run.echo_time] = []
                    if run.params:
                        run_by_echo[run.echo_time].append(run.params)

        for echo_time in run_by_echo.keys():
            if run_by_echo[echo_time]:
                reference = majority_attribute_values(run_by_echo[echo_time])
                if echo_time is None:
                    modality.set_reference(reference, force=True)
                else:
                    modality.set_reference(reference, echo_time)

        # Start calculating delta for each run
        flag_modality = True
        for subject in modality.subjects:
            flag_subject = True
            for session in subject.sessions:
                for run in session.runs:
                    reference = modality.get_reference(run.echo_time)
                    if not reference:
                        continue
                    run.delta = param_difference(run.params,
                                                 reference)
                    # run.delta = param_difference(run.params,
                    #                              reference,
                    #                              ignore=['modality',
                    #                                      'phase_encoding_direction'])
                    if run.delta:
                        modality.add_non_compliant_subject_name(subject.name)
                        dataset.add_non_compliant_modality_name(modality.name)
                        # reasons = extract_reasons(run.delta)
                        # modality.reasons_non_compliance.update(reasons)
                        store_reasons(modality, run, subject.name, session.name)
                        flag_subject = False
                        flag_modality = False
                        modality.compliant = False
            if flag_subject:
                modality.add_compliant_subject_name(subject.name)
        if flag_modality:
            modality.compliant = flag_modality
            dataset.add_compliant_modality_name(modality.name)
    return dataset


def store_reasons(modality, run, subject_name, session_name):
    for entry in run.delta:
        if entry[0] != 'change':
            continue
        _, parameter, [new_value, ref_value] = entry

        if not is_hashable(parameter):
            parameter = str(parameter)

        modality.update_reason(parameter, run.echo_time, ref_value, new_value,
                               '{}_{}'.format(subject_name, session_name))


def generate_report(dataset: Project, output_dir: Union[Path, str]) -> None:
    """
    Generates an HTML report aggregating and summarizing the non-compliance
    discovered in the dataset.

    Parameters
    ----------
    dataset : Project
        MRdataset.base.Project instance for the dataset which is to be checked
    output_dir : Union[Path, str]
        Directory in which the generated report should be stored.
    """
    output_path = Path(output_dir).resolve()
    if not Path(output_path).is_dir():
        raise OSError('Expected valid output_directory, '
                      'Got {0}'.format(output_dir))
    filename = '{}_{}.html'.format(dataset.name, timestamp())
    out_path = output_path / filename
    HtmlFormatter(filepath=out_path, params=dataset)
    print(otg_report(dataset, filename))


def otg_report(dataset, report_name):
    result = {}
    for modality in dataset.modalities:
        percent_non_compliant = len(modality.non_compliant_subject_names) \
                                / len(modality.subjects)
        if percent_non_compliant > 0:
            result[modality.name] = str(100*percent_non_compliant)

    ret_string = 'In {0} dataset, modalities "{1}" are non-compliant. ' \
                 'See {2} for report'.format(dataset.name,
                                                ", ".join(result.keys()),
                                             report_name)
    return ret_string
