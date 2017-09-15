#!/usr/bin/env python
# -*- coding: utf-8 -*-
# emacs: -*- mode: python; py-indent-offset: 4; indent-tabs-mode: nil -*-
# vi: set ft=python sts=4 ts=4 sw=4 et:
"""
NiBetaSeries processing workflows
"""
from __future__ import print_function, division, absolute_import, unicode_literals
import sys
import os
from copy import deepcopy

from .preprocess import init_derive_residuals_wf
from niworkflows.nipype.pipeline import engine as pe
from niworkflows.nipype.interfaces import utility as niu
def init_nibetaseries_participant_wf(subject_list, task_id, derivatives_pipeline,
                     bids_dir, output_dir, work_dir, space, variant, res,
                     hrf_model, slice_time_ref, run_uuid, omp_nthreads):
    """
    This workflow organizes the execution of NiBetaSeries, with a sub-workflow for
    each subject.
    .. workflow::
        from NiBetaSeries.workflows.base import init_nibetaseries_participant_wf
        wf = init_nibetaseries_participant_wf(subject_list=['NiBetaSeriesSubsTest'],
                              task_id='',
                              derivatives_pipeline='.',
                              bids_dir='.',
                              output_dir='.',
                              work_dir='.',
                              space='',
                              variant='',
                              res='',
                              hrf_model='glover',
                              slice_time_ref='0.5',
                              run_uuid='X',
                              omp_nthreads=1)
    Parameters
        subject_list : list
            List of subject labels
        task_id : str or None
            Task ID of preprocessed BOLD series to derive betas, or ``None`` to process all
        derivatives_pipeline : str
        	Directory where preprocessed derivatives live
    	bids_dir : str
            Root directory of BIDS dataset
        output_dir : str
            Directory in which to save derivatives
        work_dir : str
            Directory in which to store workflow execution state and temporary files
        space : str
        	Space of preprocessed BOLD series to derive betas, or ``None`` to process all
        variant : str
        	Variant of preprocessed BOLD series to derive betas, or ``None`` to process all
        res : str
        	resolution (XxYxZ) of preprocessed BOLD series to derive betas, or ``None`` to process all
        hrf_model : str
        	hrf model used to convolve events
        slice_time_ref : float
        	fractional representation of the slice that used as the reference during slice time correction.
        run_uuid : str
            Unique identifier for execution instance
        omp_nthreads : int
            Maximum number of threads an individual process may use
    """
    nibetaseries_participant_wf = pe.Workflow(name='nibetaseries_participant_wf')
    nibetaseries_participant_wf.base_dir = work_dir
    reportlets_dir = os.path.join(work_dir, 'reportlets')
    for subject_id in subject_list:
        single_subject_wf = init_single_subject_wf(
        subject_list=subject_list,
        task_id=task_id,
        name="single_subject_" + subject_id + "_wf",
        derivatives_pipeline=derivatives_pipeline,
        bids_dir=bids_dir,
        output_dir=output_dir,
        work_dir=work_dir,
        space=space,
        variant=variant,
        res=res,
        hrf_model=hrf_model,
        slice_time_ref=slice_time_ref,
        run_uuid=run_uuid,
        omp_nthreads=omp_nthreads
        )

        single_subject_wf.config['execution']['crashdump_dir'] = (
            os.path.join(output_dir, "nibetaseries", "sub-" + subject_id, 'log', run_uuid)
        )

        for node in single_subject_wf._get_all_nodes():
            node.config = deepcopy(single_subject_wf.config)

        fmriprep_wf.add_nodes([single_subject_wf])
    return nibetaseries_participant_wf

def init_single_subject_wf(subject_id, task_id, name, derivatives_pipeline,
                     bids_dir, output_dir, work_dir, space, variant, res,
                     hrf_model, slice_time_ref, run_uuid, omp_nthreads):
    import pkg_resources as pkgr
    from bids.grabbids import BIDSLayout
    # for querying derivatives structure
    config_file = pkgr.resource_filename('NiBetaSeries', 'utils/bids_derivatives.json')

    bids_data = BIDSLayout(bids_dir)

    derivatives_dir = os.path.join(bids_dir,'derivatives',derivatives_pipeline)
    derivatives_data = BIDSLayout(derivatives_dir,config=config_file)

    # get events file
    event_list = bids_data.get(subject=subject_id,
                               task=task_id,
                               type=events,
                               extensions='tsv',
                               return_type='file')

    if not event_list:
        raise Exception("No event files were found for participant {}".format(subject_id))
    elif len(event_list) > 1:
        raise Exception("Too many event files were found for participant {}".format(subject_id))
    else:
      events_file = event_list[0]

    # get derivatives files
    # preproc
    preproc_query = {
                     'subject': subject_id,
                     'task': task_id,
                     'type': 'preproc',
                     'return_type': 'file',
                     'extensions': ['nii', 'nii.gz']
                     }
    if variant:
        preproc_query['variant'] = variant
    if space:
        preproc_query['space'] = space
    if res:
        preproc_query['res'] = res

    preproc_list = derivatives_data.get(**preproc_query)

    if not preproc_list:
        raise Exception("No preproc files were found for participant {}".format(subject_id))
    elif len(preproc_list) > 1:
        raise Exception("Too many preproc files were found for participant {}".format(subject_id))
    else:
        preproc_file = preproc_list[0]
    # confounds
    confounds_list = derivatives_data.get(subject=subject_id,
                               task=task_id,
                               type=confounds,
                               extensions='tsv',
                               return_type='file')
    if not confounds_list:
        raise Exception("No confound files were found for participant {}".format(subject_id))
    elif len(confounds_list) > 1:
        raise Exception("Too many confound files were found for participant {}".format(subject_id))
    else:
        confound_file = confound_list[0]

    # brainmask
    brainmask_query = {
                     'subject': subject_id,
                     'task': task_id,
                     'type': 'brainmask',
                     'return_type': 'file',
                     'extensions': ['nii', 'nii.gz']
                     }
    if space:
        brainmask_query['space'] = space
    if res:
        brainmask_query['res'] = res

    brainmask_list = derivatives_data.get(**brainmask_query)
    if not brainmask_list:
        raise Exception("No brainmask files were found for participant {}".format(subject_id))
    elif len(brainmask_list) > 1:
        raise Exception("Too many brainmask files were found for participant {}".format(subject_id))
    else:
        brainmask_file = brainmask_list[0]

    workflow = pe.Workflow(name=name)

    inputnode = pe.Node(niu.IdentityInterface(fields=['subjects_dir']),
                        name='inputnode')


    #bidssrc = pe.Node(BIDSDataGrabber(subject_data=subject_data, anat_only=anat_only),
    #                  name='bidssrc')

    #bids_info = pe.Node(BIDSInfo(), name='bids_info', run_without_submitting=True)

    #summary = pe.Node(SubjectSummary(output_spaces=output_spaces, template=template),
    #                  name='summary', run_without_submitting=True)

    #about = pe.Node(AboutSummary(version=__version__,
    #                             command=' '.join(sys.argv)),
    #                name='about', run_without_submitting=True)

    #ds_summary_report = pe.Node(
    #    DerivativesDataSink(base_directory=reportlets_dir,
    #                        suffix='summary'),
    #    name='ds_summary_report', run_without_submitting=True)

    #ds_about_report = pe.Node(
    #    DerivativesDataSink(base_directory=reportlets_dir,
    #                        suffix='about'),
    #    name='ds_about_report', run_without_submitting=True)
