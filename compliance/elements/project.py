from compliance.elements.slice import Node, parse
import warnings
import dictdiffer
from pathlib import Path
from compliance.templates import formatter
from compliance.utils import functional


def check_compliance(dataset,
                     strategy='first',
                     output_dir=None,
                     reference_path=None,
                     reindex=False,
                     verbose=False):
    root_node = Node(dataset.data_root)
    if dataset.name is None:
        if dataset.projects:
            root_node.name = dataset.projects[0]
    else:
        root_node.name = dataset.name

    root_node = construct_tree(dataset, root_node)
    root_node = partition_sessions_by_first(root_node)
    generate_report(root_node, output_dir, dataset.name)


def construct_tree(dataset, root_node):
    for mode in dataset.modalities:
        modality = Node(path=None)
        modality.name = mode
        for subject_id in dataset.modalities[mode]:
            data = dataset[subject_id, mode]
            if len(data['files']) == 0:
                run_node = Node(path=None)
                run_node.error = True
                warnings.warn("Expected at least 1 .dcm files. "
                              "Got 0 for Subject : {0} and Modality : {1}".format(subject_id, mode),
                              stacklevel=2)
                continue
            elif len(data['files']) == 1:
                run_node = Node(path=data['files'][0])
                run_node.error = False
                run_node.name = subject_id
                modality.insert(run_node)
            else:
                run_node = parse(data['files'][0])
                flag = False
                for f in data['files'][1:]:
                    temp_node = parse(f)
                    difference = list(dictdiffer.diff(dict(run_node.params), dict(temp_node.params)))
                    if difference:
                        flag = True
                        warnings.warn("Expected all .dcm files to have same parameters. "
                                      "Got different values in Subject : {0}"
                                      " Modality : {1}".format(subject_id, mode),
                                      stacklevel=2)
                        break
                run_node.error = flag
                run_node.path = Path(data['files'][0]).parent
                run_node.name = subject_id
                if not run_node.error:
                    modality.insert(run_node)
        root_node.insert(modality)
    return root_node


def partition_sessions_by_first(root_node):
    for mode in root_node.children:
        i = 0
        anchor = None
        if count_zero_children(mode):
            continue
        for i, c in enumerate(mode.children):
            if not c.error:
                anchor = c
                break
        mode.params = anchor.params.copy()
        for sub in mode.children[i:]:
            sub.delta = list(dictdiffer.diff(dict(anchor.params), dict(sub.params)))
            if sub.delta:
                sub.consistent = False
                mode.bad_children.append(sub.name)
            else:
                sub.consistent = True
                mode.good_children.append(sub.name)
    return root_node


def count_zero_children(node):
    """
    Node has zero children
    """
    if len(node.children) == 0:
        warnings.warn("No consistent runs found for node : {0}".format(node.name),
                      stacklevel=2)
        return True
    return False


def partition_sessions_by_majority(root_node):
    for mode in root_node.children:
        i = 0
        anchor = None
        if count_zero_children(mode):
            continue


def generate_report(root_node, output_dir, name):
    formatter.HtmlFormatter(filepath=Path(output_dir) / (
        '{0}_{1}.{2}'.format(name,
                             functional.timestamp(),
                             'html')
    ), params=root_node)
