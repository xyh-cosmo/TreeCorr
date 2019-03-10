# Copyright (c) 2003-2015 by Mike Jarvis
#
# TreeCorr is free software: redistribution and use in source and binary forms,
# with or without modification, are permitted provided that the following
# conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions, and the disclaimer given in the accompanying LICENSE
#    file.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions, and the disclaimer given in the documentation
#    and/or other materials provided with the distribution.

from __future__ import print_function
import numpy as np
import treecorr
import os
import sys
import fitsio
import coord

from test_helper import get_script_name, do_pickle, CaptureLog, assert_raises
from numpy import sin, cos, tan, arcsin, arccos, arctan, arctan2, pi

def test_direct():
    # If the catalogs are small enough, we can do a direct calculation to see if comes out right.
    # This should exactly match the treecorr result if bin_slop=0.

    ngal = 200
    s = 10.
    np.random.seed(8675309)
    x1 = np.random.normal(0,s, (ngal,) )
    y1 = np.random.normal(0,s, (ngal,) )
    w1 = np.random.random(ngal)

    x2 = np.random.normal(0,s, (ngal,) )
    y2 = np.random.normal(0,s, (ngal,) )
    w2 = np.random.random(ngal)
    g12 = np.random.normal(0,0.2, (ngal,) )
    g22 = np.random.normal(0,0.2, (ngal,) )

    cat1 = treecorr.Catalog(x=x1, y=y1, w=w1)
    cat2 = treecorr.Catalog(x=x2, y=y2, w=w2, g1=g12, g2=g22)

    min_sep = 1.
    max_sep = 50.
    nbins = 50
    bin_size = np.log(max_sep/min_sep) / nbins
    ng = treecorr.NGCorrelation(min_sep=min_sep, max_sep=max_sep, nbins=nbins, bin_slop=0.)
    ng.process(cat1, cat2)

    true_npairs = np.zeros(nbins, dtype=int)
    true_weight = np.zeros(nbins, dtype=float)
    true_xi = np.zeros(nbins, dtype=complex)
    for i in range(ngal):
        # It's hard to do all the pairs at once with numpy operations (although maybe possible).
        # But we can at least do all the pairs for each entry in cat1 at once with arrays.
        rsq = (x1[i]-x2)**2 + (y1[i]-y2)**2
        r = np.sqrt(rsq)
        logr = np.log(r)
        expmialpha = ((x1[i]-x2) - 1j*(y1[i]-y2)) / r

        ww = w1[i] * w2
        xi = -ww * (g12 + 1j*g22) * expmialpha**2

        index = np.floor(np.log(r/min_sep) / bin_size).astype(int)
        mask = (index >= 0) & (index < nbins)
        np.add.at(true_npairs, index[mask], 1)
        np.add.at(true_weight, index[mask], ww[mask])
        np.add.at(true_xi, index[mask], xi[mask])

    true_xi /= true_weight

    print('true_npairs = ',true_npairs)
    print('diff = ',ng.npairs - true_npairs)
    np.testing.assert_array_equal(ng.npairs, true_npairs)

    print('true_weight = ',true_weight)
    print('diff = ',ng.weight - true_weight)
    np.testing.assert_allclose(ng.weight, true_weight, rtol=1.e-5, atol=1.e-8)

    print('true_xi = ',true_xi)
    print('ng.xi = ',ng.xi)
    print('ng.xi_im = ',ng.xi_im)
    np.testing.assert_allclose(ng.xi, true_xi.real, rtol=1.e-4, atol=1.e-8)
    np.testing.assert_allclose(ng.xi_im, true_xi.imag, rtol=1.e-4, atol=1.e-8)

    # Check that running via the corr2 script works correctly.
    config = treecorr.config.read_config('configs/ng_direct.yaml')
    cat1.write(config['file_name'])
    cat2.write(config['file_name2'])
    treecorr.corr2(config)
    data = fitsio.read(config['ng_file_name'])
    np.testing.assert_allclose(data['R_nom'], ng.rnom)
    np.testing.assert_allclose(data['npairs'], ng.npairs)
    np.testing.assert_allclose(data['weight'], ng.weight)
    np.testing.assert_allclose(data['gamT'], ng.xi, rtol=1.e-3)
    np.testing.assert_allclose(data['gamX'], ng.xi_im, rtol=1.e-3)

    # Repeat with binslop not precisely 0, since the code flow is different for bin_slop == 0.
    # And don't do any top-level recursion so we actually test not going to the leaves.
    ng = treecorr.NGCorrelation(min_sep=min_sep, max_sep=max_sep, nbins=nbins, bin_slop=1.e-16,
                                max_top=0)
    ng.process(cat1, cat2)
    np.testing.assert_array_equal(ng.npairs, true_npairs)
    np.testing.assert_allclose(ng.weight, true_weight, rtol=1.e-5, atol=1.e-8)
    np.testing.assert_allclose(ng.xi, true_xi.real, rtol=1.e-3, atol=3.e-4)
    np.testing.assert_allclose(ng.xi_im, true_xi.imag, atol=3.e-4)

    # Check a few basic operations with a NGCorrelation object.
    do_pickle(ng)

    ng2 = ng.copy()
    ng2 += ng
    np.testing.assert_allclose(ng2.npairs, 2*ng.npairs)
    np.testing.assert_allclose(ng2.weight, 2*ng.weight)
    np.testing.assert_allclose(ng2.meanr, 2*ng.meanr)
    np.testing.assert_allclose(ng2.meanlogr, 2*ng.meanlogr)
    np.testing.assert_allclose(ng2.xi, 2*ng.xi)
    np.testing.assert_allclose(ng2.xi_im, 2*ng.xi_im)

    ng2.clear()
    ng2 += ng
    np.testing.assert_allclose(ng2.npairs, ng.npairs)
    np.testing.assert_allclose(ng2.weight, ng.weight)
    np.testing.assert_allclose(ng2.meanr, ng.meanr)
    np.testing.assert_allclose(ng2.meanlogr, ng.meanlogr)
    np.testing.assert_allclose(ng2.xi, ng.xi)
    np.testing.assert_allclose(ng2.xi_im, ng.xi_im)

    ascii_name = 'output/ng_ascii.txt'
    ng.write(ascii_name, precision=16)
    ng3 = treecorr.NGCorrelation(min_sep=min_sep, max_sep=max_sep, nbins=nbins)
    ng3.read(ascii_name)
    np.testing.assert_allclose(ng3.npairs, ng.npairs)
    np.testing.assert_allclose(ng3.weight, ng.weight)
    np.testing.assert_allclose(ng3.meanr, ng.meanr)
    np.testing.assert_allclose(ng3.meanlogr, ng.meanlogr)
    np.testing.assert_allclose(ng3.xi, ng.xi)
    np.testing.assert_allclose(ng3.xi_im, ng.xi_im)

    fits_name = 'output/ng_fits.fits'
    ng.write(fits_name)
    ng4 = treecorr.NGCorrelation(min_sep=min_sep, max_sep=max_sep, nbins=nbins)
    ng4.read(fits_name)
    np.testing.assert_allclose(ng4.npairs, ng.npairs)
    np.testing.assert_allclose(ng4.weight, ng.weight)
    np.testing.assert_allclose(ng4.meanr, ng.meanr)
    np.testing.assert_allclose(ng4.meanlogr, ng.meanlogr)
    np.testing.assert_allclose(ng4.xi, ng.xi)
    np.testing.assert_allclose(ng4.xi_im, ng.xi_im)


def test_direct_spherical():
    # Repeat in spherical coords

    ngal = 100
    s = 10.
    np.random.seed(8675309)
    x1 = np.random.normal(0,s, (ngal,) )
    y1 = np.random.normal(0,s, (ngal,) ) + 200  # Put everything at large y, so small angle on sky
    z1 = np.random.normal(0,s, (ngal,) )
    w1 = np.random.random(ngal)

    x2 = np.random.normal(0,s, (ngal,) )
    y2 = np.random.normal(0,s, (ngal,) ) + 200
    z2 = np.random.normal(0,s, (ngal,) )
    w2 = np.random.random(ngal)
    g12 = np.random.normal(0,0.2, (ngal,) )
    g22 = np.random.normal(0,0.2, (ngal,) )

    ra1, dec1 = coord.CelestialCoord.xyz_to_radec(x1,y1,z1)
    ra2, dec2 = coord.CelestialCoord.xyz_to_radec(x2,y2,z2)

    cat1 = treecorr.Catalog(ra=ra1, dec=dec1, ra_units='rad', dec_units='rad', w=w1)
    cat2 = treecorr.Catalog(ra=ra2, dec=dec2, ra_units='rad', dec_units='rad', w=w2, g1=g12, g2=g22)

    min_sep = 1.
    max_sep = 10.
    nbins = 50
    bin_size = np.log(max_sep/min_sep) / nbins
    ng = treecorr.NGCorrelation(min_sep=min_sep, max_sep=max_sep, nbins=nbins,
                                sep_units='deg', bin_slop=0.)
    ng.process(cat1, cat2)

    r1 = np.sqrt(x1**2 + y1**2 + z1**2)
    r2 = np.sqrt(x2**2 + y2**2 + z2**2)
    x1 /= r1;  y1 /= r1;  z1 /= r1
    x2 /= r2;  y2 /= r2;  z2 /= r2

    north_pole = coord.CelestialCoord(0*coord.radians, 90*coord.degrees)

    true_npairs = np.zeros(nbins, dtype=int)
    true_weight = np.zeros(nbins, dtype=float)
    true_xi = np.zeros(nbins, dtype=complex)

    c1 = [coord.CelestialCoord(r*coord.radians, d*coord.radians) for (r,d) in zip(ra1, dec1)]
    c2 = [coord.CelestialCoord(r*coord.radians, d*coord.radians) for (r,d) in zip(ra2, dec2)]
    for i in range(ngal):
        for j in range(ngal):
            rsq = (x1[i]-x2[j])**2 + (y1[i]-y2[j])**2 + (z1[i]-z2[j])**2
            r = np.sqrt(rsq)
            r *= coord.radians / coord.degrees
            logr = np.log(r)

            index = np.floor(np.log(r/min_sep) / bin_size).astype(int)
            if index < 0 or index >= nbins:
                continue

            # Rotate shears to coordinates where line connecting is horizontal.
            # Original orientation is where north is up.
            theta1 = 90*coord.degrees - c1[i].angleBetween(north_pole, c2[j])
            theta2 = 90*coord.degrees - c2[j].angleBetween(c1[i], north_pole)
            exp2theta1 = np.cos(2*theta1) + 1j * np.sin(2*theta1)
            expm2theta2 = np.cos(2*theta2) - 1j * np.sin(2*theta2)

            g2 = g12[j] + 1j * g22[j]
            g2 *= expm2theta2

            ww = w1[i] * w2[j]
            xi = -w1[i] * w2[j] * g2

            true_npairs[index] += 1
            true_weight[index] += ww
            true_xi[index] += xi

    true_xi /= true_weight

    print('true_npairs = ',true_npairs)
    print('diff = ',ng.npairs - true_npairs)
    np.testing.assert_array_equal(ng.npairs, true_npairs)

    print('true_weight = ',true_weight)
    print('diff = ',ng.weight - true_weight)
    np.testing.assert_allclose(ng.weight, true_weight, rtol=1.e-5, atol=1.e-8)

    print('true_xi = ',true_xi)
    print('ng.xi = ',ng.xi)
    print('ng.xi_im = ',ng.xi_im)
    np.testing.assert_allclose(ng.xi, true_xi.real, rtol=1.e-4, atol=1.e-8)
    np.testing.assert_allclose(ng.xi_im, true_xi.imag, rtol=1.e-4, atol=1.e-8)

    # Check that running via the corr2 script works correctly.
    config = treecorr.config.read_config('configs/ng_direct_spherical.yaml')
    cat1.write(config['file_name'])
    cat2.write(config['file_name2'])
    treecorr.corr2(config)
    data = fitsio.read(config['ng_file_name'])
    np.testing.assert_allclose(data['R_nom'], ng.rnom)
    np.testing.assert_allclose(data['npairs'], ng.npairs)
    np.testing.assert_allclose(data['weight'], ng.weight)
    np.testing.assert_allclose(data['gamT'], ng.xi, rtol=1.e-3)
    np.testing.assert_allclose(data['gamX'], ng.xi_im, rtol=1.e-3)

    # Repeat with binslop not precisely 0, since the code flow is different for bin_slop == 0.
    # And don't do any top-level recursion so we actually test not going to the leaves.
    ng = treecorr.NGCorrelation(min_sep=min_sep, max_sep=max_sep, nbins=nbins,
                                sep_units='deg', bin_slop=1.e-16, max_top=0)
    ng.process(cat1, cat2)
    np.testing.assert_array_equal(ng.npairs, true_npairs)
    np.testing.assert_allclose(ng.weight, true_weight, rtol=1.e-5, atol=1.e-8)
    np.testing.assert_allclose(ng.xi, true_xi.real, rtol=1.e-3, atol=2.e-4)
    np.testing.assert_allclose(ng.xi_im, true_xi.imag, atol=2.e-4)


def test_pairwise():
    # Test the pairwise option.

    ngal = 1000
    s = 10.
    np.random.seed(8675309)
    x1 = np.random.normal(0,s, (ngal,) )
    y1 = np.random.normal(0,s, (ngal,) )
    w1 = np.random.random(ngal)

    x2 = np.random.normal(0,s, (ngal,) )
    y2 = np.random.normal(0,s, (ngal,) )
    w2 = np.random.random(ngal)
    g12 = np.random.normal(0,0.2, (ngal,) )
    g22 = np.random.normal(0,0.2, (ngal,) )

    w1 = np.ones_like(w1)
    w2 = np.ones_like(w2)

    cat1 = treecorr.Catalog(x=x1, y=y1, w=w1)
    cat2 = treecorr.Catalog(x=x2, y=y2, w=w2, g1=g12, g2=g22)

    min_sep = 5.
    max_sep = 50.
    nbins = 10
    bin_size = np.log(max_sep/min_sep) / nbins
    ng = treecorr.NGCorrelation(min_sep=min_sep, max_sep=max_sep, nbins=nbins)
    ng.process_pairwise(cat1, cat2)
    ng.finalize(cat2.varg)

    true_npairs = np.zeros(nbins, dtype=int)
    true_weight = np.zeros(nbins, dtype=float)
    true_xi = np.zeros(nbins, dtype=complex)

    rsq = (x1-x2)**2 + (y1-y2)**2
    r = np.sqrt(rsq)
    logr = np.log(r)
    expmialpha = ((x1-x2) - 1j*(y1-y2)) / r

    ww = w1 * w2
    xi = -ww * (g12 - 1j*g22) * expmialpha**2

    index = np.floor(np.log(r/min_sep) / bin_size).astype(int)
    mask = (index >= 0) & (index < nbins)
    np.add.at(true_npairs, index[mask], 1)
    np.add.at(true_weight, index[mask], ww[mask])
    np.add.at(true_xi, index[mask], xi[mask])

    true_xi /= true_weight

    np.testing.assert_array_equal(ng.npairs, true_npairs)
    np.testing.assert_allclose(ng.weight, true_weight, rtol=1.e-5, atol=1.e-8)
    np.testing.assert_allclose(ng.xi, true_xi.real, rtol=1.e-4, atol=1.e-8)
    np.testing.assert_allclose(ng.xi_im, true_xi.imag, rtol=1.e-4, atol=1.e-8)

    # If cats have names, then the logger will mention them.
    # Also, test running with optional args.
    cat1.name = "first"
    cat2.name = "second"
    with CaptureLog() as cl:
        ng.logger = cl.logger
        ng.process_pairwise(cat1, cat2, metric='Euclidean', num_threads=2)
    assert "for cats first, second" in cl.output


def test_single():
    # Use gamma_t(r) = gamma0 exp(-r^2/2r0^2) around a single lens
    # i.e. gamma(r) = -gamma0 exp(-r^2/2r0^2) (x+iy)^2/r^2

    nsource = 300000
    gamma0 = 0.05
    r0 = 10.
    L = 5. * r0
    np.random.seed(8675309)
    x = (np.random.random_sample(nsource)-0.5) * L
    y = (np.random.random_sample(nsource)-0.5) * L
    r2 = (x**2 + y**2)
    gammat = gamma0 * np.exp(-0.5*r2/r0**2)
    g1 = -gammat * (x**2-y**2)/r2
    g2 = -gammat * (2.*x*y)/r2

    lens_cat = treecorr.Catalog(x=[0], y=[0], x_units='arcmin', y_units='arcmin')
    source_cat = treecorr.Catalog(x=x, y=y, g1=g1, g2=g2, x_units='arcmin', y_units='arcmin')
    ng = treecorr.NGCorrelation(bin_size=0.1, min_sep=1., max_sep=20., sep_units='arcmin',
                                verbose=1)
    ng.process(lens_cat, source_cat)

    # log(<R>) != <logR>, but it should be close:
    print('meanlogr - log(meanr) = ',ng.meanlogr - np.log(ng.meanr))
    np.testing.assert_allclose(ng.meanlogr, np.log(ng.meanr), atol=1.e-3)

    r = ng.meanr
    true_gt = gamma0 * np.exp(-0.5*r**2/r0**2)

    print('ng.xi = ',ng.xi)
    print('ng.xi_im = ',ng.xi_im)
    print('true_gammat = ',true_gt)
    print('ratio = ',ng.xi / true_gt)
    print('diff = ',ng.xi - true_gt)
    print('max diff = ',max(abs(ng.xi - true_gt)))
    np.testing.assert_allclose(ng.xi, true_gt, rtol=3.e-2)
    np.testing.assert_allclose(ng.xi_im, 0, atol=1.e-4)

    # Check that we get the same result using the corr2 function:
    lens_cat.write(os.path.join('data','ng_single_lens.dat'))
    source_cat.write(os.path.join('data','ng_single_source.dat'))
    config = treecorr.read_config('configs/ng_single.yaml')
    config['verbose'] = 0
    treecorr.corr2(config)
    corr2_output = np.genfromtxt(os.path.join('output','ng_single.out'), names=True,
                                    skip_header=1)
    print('ng.xi = ',ng.xi)
    print('from corr2 output = ',corr2_output['gamT'])
    print('ratio = ',corr2_output['gamT']/ng.xi)
    print('diff = ',corr2_output['gamT']-ng.xi)
    print('xi_im from corr2 output = ',corr2_output['gamX'])
    np.testing.assert_allclose(corr2_output['gamT'], ng.xi, rtol=1.e-3)
    np.testing.assert_allclose(corr2_output['gamX'], 0, atol=1.e-4)

    # Check that adding results with different coords or metric emits a warning.
    lens_cat2 = treecorr.Catalog(x=[0], y=[0], z=[0])
    source_cat2 = treecorr.Catalog(x=x, y=y, z=x, g1=g1, g2=g2)
    with CaptureLog() as cl:
        ng2 = treecorr.NGCorrelation(bin_size=0.1, min_sep=1., max_sep=20., logger=cl.logger)
        ng2.process_cross(lens_cat2, source_cat2)
        ng2 += ng
    assert "Detected a change in catalog coordinate systems" in cl.output

    with CaptureLog() as cl:
        ng3 = treecorr.NGCorrelation(bin_size=0.1, min_sep=1., max_sep=20., logger=cl.logger)
        ng3.process_cross(lens_cat2, source_cat2, metric='Rperp')
        ng3 += ng2
    assert "Detected a change in metric" in cl.output

    # There is special handling for single-row catalogs when using np.genfromtxt rather
    # than pandas.  So mock it up to make sure we test it.
    if sys.version_info < (3,): return  # mock only available on python 3
    from unittest import mock
    with mock.patch.dict(sys.modules, {'pandas':None}):
        with CaptureLog() as cl:
            treecorr.corr2(config, logger=cl.logger)
        assert "Unable to import pandas" in cl.output
    corr2_output = np.genfromtxt(os.path.join('output','ng_single.out'), names=True,
                                    skip_header=1)
    np.testing.assert_allclose(corr2_output['gamT'], ng.xi, rtol=1.e-3)



def test_pairwise():
    # Test the same profile, but with the pairwise calcualtion:
    nsource = 300000
    gamma0 = 0.05
    r0 = 10.
    L = 5. * r0
    np.random.seed(8675309)
    x = (np.random.random_sample(nsource)-0.5) * L
    y = (np.random.random_sample(nsource)-0.5) * L
    r2 = (x**2 + y**2)
    gammat = gamma0 * np.exp(-0.5*r2/r0**2)
    g1 = -gammat * (x**2-y**2)/r2
    g2 = -gammat * (2.*x*y)/r2

    dx = (np.random.random_sample(nsource)-0.5) * L
    dx = (np.random.random_sample(nsource)-0.5) * L

    lens_cat = treecorr.Catalog(x=dx, y=dx, x_units='arcmin', y_units='arcmin')
    source_cat = treecorr.Catalog(x=x+dx, y=y+dx, g1=g1, g2=g2, x_units='arcmin', y_units='arcmin')
    ng = treecorr.NGCorrelation(bin_size=0.1, min_sep=1., max_sep=20., sep_units='arcmin',
                                verbose=1, pairwise=True)
    ng.process(lens_cat, source_cat)

    r = ng.meanr
    true_gt = gamma0 * np.exp(-0.5*r**2/r0**2)

    print('ng.xi = ',ng.xi)
    print('ng.xi_im = ',ng.xi_im)
    print('true_gammat = ',true_gt)
    print('ratio = ',ng.xi / true_gt)
    print('diff = ',ng.xi - true_gt)
    print('max diff = ',max(abs(ng.xi - true_gt)))
    # I don't really understand why this comes out slightly less accurate.
    # I would have thought it would be slightly more accurate because it doesn't use the
    # approximations intrinsic to the tree calculation.
    np.testing.assert_allclose(ng.xi, true_gt, rtol=3.e-2)
    np.testing.assert_allclose(ng.xi_im, 0, atol=1.e-4)

    # Check that we get the same result using the corr2 function:
    lens_cat.write(os.path.join('data','ng_pairwise_lens.dat'))
    source_cat.write(os.path.join('data','ng_pairwise_source.dat'))
    config = treecorr.read_config('configs/ng_pairwise.yaml')
    config['verbose'] = 0
    treecorr.corr2(config)
    corr2_output = np.genfromtxt(os.path.join('output','ng_pairwise.out'), names=True,
                                    skip_header=1)
    print('ng.xi = ',ng.xi)
    print('from corr2 output = ',corr2_output['gamT'])
    print('ratio = ',corr2_output['gamT']/ng.xi)
    print('diff = ',corr2_output['gamT']-ng.xi)
    np.testing.assert_allclose(corr2_output['gamT'], ng.xi, rtol=1.e-3)

    print('xi_im from corr2 output = ',corr2_output['gamX'])
    np.testing.assert_allclose(corr2_output['gamX'], 0, atol=1.e-4)


def test_spherical():
    # This is the same profile we used for test_single, but put into spherical coords.
    # We do the spherical trig by hand using the obvious formulae, rather than the clever
    # optimizations that are used by the TreeCorr code, thus serving as a useful test of
    # the latter.

    nsource = 300000
    gamma0 = 0.05
    r0 = 10. * coord.degrees / coord.radians
    L = 5. * r0
    np.random.seed(8675309)
    x = (np.random.random_sample(nsource)-0.5) * L
    y = (np.random.random_sample(nsource)-0.5) * L
    r2 = (x**2 + y**2)
    gammat = gamma0 * np.exp(-0.5*r2/r0**2)
    g1 = -gammat * (x**2-y**2)/r2
    g2 = -gammat * (2.*x*y)/r2
    r = np.sqrt(r2)
    theta = arctan2(y,x)

    ng = treecorr.NGCorrelation(bin_size=0.1, min_sep=1., max_sep=20., sep_units='deg',
                                verbose=1)
    r1 = np.exp(ng.logr) * (coord.degrees / coord.radians)
    true_gt = gamma0 * np.exp(-0.5*r1**2/r0**2)

    # Test this around several central points
    if __name__ == '__main__':
        ra0_list = [ 0., 1., 1.3, 232., 0. ]
        dec0_list = [ 0., -0.3, 1.3, -1.4, pi/2.-1.e-6 ]
    else:
        ra0_list = [ 232 ]
        dec0_list = [ -1.4 ]
    for ra0, dec0 in zip(ra0_list, dec0_list):

        # Use spherical triangle with A = point, B = (ra0,dec0), C = N. pole
        # a = Pi/2-dec0
        # c = 2*asin(r/2)  (lambert projection)
        # B = Pi/2 - theta

        c = 2.*arcsin(r/2.)
        a = pi/2. - dec0
        B = pi/2. - theta
        B[x<0] *= -1.
        B[B<-pi] += 2.*pi
        B[B>pi] -= 2.*pi

        # Solve the rest of the triangle with spherical trig:
        cosb = cos(a)*cos(c) + sin(a)*sin(c)*cos(B)
        b = arccos(cosb)
        cosA = (cos(a) - cos(b)*cos(c)) / (sin(b)*sin(c))
        #A = arccos(cosA)
        A = np.zeros_like(cosA)
        A[abs(cosA)<1] = arccos(cosA[abs(cosA)<1])
        A[cosA<=-1] = pi
        cosC = (cos(c) - cos(a)*cos(b)) / (sin(a)*sin(b))
        #C = arccos(cosC)
        C = np.zeros_like(cosC)
        C[abs(cosC)<1] = arccos(cosC[abs(cosC)<1])
        C[cosC<=-1] = pi
        C[x<0] *= -1.

        ra = ra0 - C
        dec = pi/2. - b

        # Rotate shear relative to local west
        # gamma_sph = exp(2i beta) * gamma
        # where beta = pi - (A+B) is the angle between north and "up" in the tangent plane.
        beta = pi - (A+B)
        beta[x>0] *= -1.
        cos2beta = cos(2.*beta)
        sin2beta = sin(2.*beta)
        g1_sph = g1 * cos2beta - g2 * sin2beta
        g2_sph = g2 * cos2beta + g1 * sin2beta

        lens_cat = treecorr.Catalog(ra=[ra0], dec=[dec0], ra_units='rad', dec_units='rad')
        source_cat = treecorr.Catalog(ra=ra, dec=dec, g1=g1_sph, g2=g2_sph,
                                      ra_units='rad', dec_units='rad')
        ng.process(lens_cat, source_cat)

        print('ra0, dec0 = ',ra0,dec0)
        print('ng.xi = ',ng.xi)
        print('true_gammat = ',true_gt)
        print('ratio = ',ng.xi / true_gt)
        print('diff = ',ng.xi - true_gt)
        print('max diff = ',max(abs(ng.xi - true_gt)))
        # The 3rd and 4th centers are somewhat less accurate.  Not sure why.
        # The math seems to be right, since the last one that gets all the way to the pole
        # works, so I'm not sure what is going on.  It's just a few bins that get a bit less
        # accurate.  Possibly worth investigating further at some point...
        np.testing.assert_allclose(ng.xi, true_gt, rtol=0.1)

    # One more center that can be done very easily.  If the center is the north pole, then all
    # the tangential shears are pure (positive) g1.
    ra0 = 0
    dec0 = pi/2.
    ra = theta
    dec = pi/2. - 2.*arcsin(r/2.)

    lens_cat = treecorr.Catalog(ra=[ra0], dec=[dec0], ra_units='rad', dec_units='rad')
    source_cat = treecorr.Catalog(ra=ra, dec=dec, g1=gammat, g2=np.zeros_like(gammat),
                                  ra_units='rad', dec_units='rad')
    ng.process(lens_cat, source_cat)

    print('ng.xi = ',ng.xi)
    print('ng.xi_im = ',ng.xi_im)
    print('true_gammat = ',true_gt)
    print('ratio = ',ng.xi / true_gt)
    print('diff = ',ng.xi - true_gt)
    print('max diff = ',max(abs(ng.xi - true_gt)))
    np.testing.assert_allclose(ng.xi, true_gt, rtol=0.1)
    np.testing.assert_allclose(ng.xi_im, 0, atol=1.e-4)

    # Check that we get the same result using the corr2 function:
    lens_cat.write(os.path.join('data','ng_spherical_lens.dat'))
    source_cat.write(os.path.join('data','ng_spherical_source.dat'))
    config = treecorr.read_config('configs/ng_spherical.yaml')
    config['verbose'] = 0
    treecorr.corr2(config)
    corr2_output = np.genfromtxt(os.path.join('output','ng_spherical.out'), names=True,
                                    skip_header=1)
    print('ng.xi = ',ng.xi)
    print('from corr2 output = ',corr2_output['gamT'])
    print('ratio = ',corr2_output['gamT']/ng.xi)
    print('diff = ',corr2_output['gamT']-ng.xi)
    np.testing.assert_allclose(corr2_output['gamT'], ng.xi, rtol=1.e-3)

    print('xi_im from corr2 output = ',corr2_output['gamX'])
    np.testing.assert_allclose(corr2_output['gamX'], 0., atol=3.e-5)


def test_ng():
    # Use gamma_t(r) = gamma0 exp(-r^2/2r0^2) around a bunch of foreground lenses.
    # i.e. gamma(r) = -gamma0 exp(-r^2/2r0^2) (x+iy)^2/r^2

    nlens = 1000
    nsource = 100000
    gamma0 = 0.05
    r0 = 10.
    L = 50. * r0
    np.random.seed(8675309)
    xl = (np.random.random_sample(nlens)-0.5) * L
    yl = (np.random.random_sample(nlens)-0.5) * L
    xs = (np.random.random_sample(nsource)-0.5) * L
    ys = (np.random.random_sample(nsource)-0.5) * L
    g1 = np.zeros( (nsource,) )
    g2 = np.zeros( (nsource,) )
    for x,y in zip(xl,yl):
        dx = xs-x
        dy = ys-y
        r2 = dx**2 + dy**2
        gammat = gamma0 * np.exp(-0.5*r2/r0**2)
        g1 += -gammat * (dx**2-dy**2)/r2
        g2 += -gammat * (2.*dx*dy)/r2

    lens_cat = treecorr.Catalog(x=xl, y=yl, x_units='arcmin', y_units='arcmin')
    source_cat = treecorr.Catalog(x=xs, y=ys, g1=g1, g2=g2, x_units='arcmin', y_units='arcmin')
    ng = treecorr.NGCorrelation(bin_size=0.1, min_sep=1., max_sep=20., sep_units='arcmin',
                                verbose=1)
    ng.process(lens_cat, source_cat)

    r = ng.meanr
    true_gt = gamma0 * np.exp(-0.5*r**2/r0**2)

    print('ng.xi = ',ng.xi)
    print('ng.xi_im = ',ng.xi_im)
    print('true_gammat = ',true_gt)
    print('ratio = ',ng.xi / true_gt)
    print('diff = ',ng.xi - true_gt)
    print('max diff = ',max(abs(ng.xi - true_gt)))
    np.testing.assert_allclose(ng.xi, true_gt, rtol=0.1)
    np.testing.assert_allclose(ng.xi_im, 0, atol=5.e-3)

    nrand = nlens * 3
    xr = (np.random.random_sample(nrand)-0.5) * L
    yr = (np.random.random_sample(nrand)-0.5) * L
    rand_cat = treecorr.Catalog(x=xr, y=yr, x_units='arcmin', y_units='arcmin')
    rg = treecorr.NGCorrelation(bin_size=0.1, min_sep=1., max_sep=20., sep_units='arcmin',
                                verbose=1)
    rg.process(rand_cat, source_cat)
    print('rg.xi = ',rg.xi)
    xi, xi_im, varxi = ng.calculateXi(rg)
    print('compensated xi = ',xi)
    print('compensated xi_im = ',xi_im)
    print('true_gammat = ',true_gt)
    print('ratio = ',xi / true_gt)
    print('diff = ',xi - true_gt)
    print('max diff = ',max(abs(xi - true_gt)))
    # It turns out this doesn't come out much better.  I think the imprecision is mostly just due
    # to the smallish number of lenses, not to edge effects
    np.testing.assert_allclose(xi, true_gt, rtol=0.1)
    np.testing.assert_allclose(xi_im, 0, atol=5.e-3)

    # Check that we get the same result using the corr2 function:
    lens_cat.write(os.path.join('data','ng_lens.fits'))
    source_cat.write(os.path.join('data','ng_source.fits'))
    rand_cat.write(os.path.join('data','ng_rand.fits'))
    config = treecorr.read_config('configs/ng.yaml')
    config['verbose'] = 0
    config['precision'] = 8
    treecorr.corr2(config)
    corr2_output = np.genfromtxt(os.path.join('output','ng.out'), names=True, skip_header=1)
    print('ng.xi = ',ng.xi)
    print('xi = ',xi)
    print('from corr2 output = ',corr2_output['gamT'])
    print('ratio = ',corr2_output['gamT']/xi)
    print('diff = ',corr2_output['gamT']-xi)
    np.testing.assert_allclose(corr2_output['gamT'], xi, rtol=1.e-3)
    print('xi_im from corr2 output = ',corr2_output['gamX'])
    np.testing.assert_allclose(corr2_output['gamX'], 0., atol=4.e-3)

    # In the corr2 context, you can turn off the compensated bit, even if there are randoms
    # (e.g. maybe you only want randoms for some nn calculation, but not ng.)
    config['ng_statistic'] = 'simple'
    treecorr.corr2(config)
    corr2_output = np.genfromtxt(os.path.join('output','ng.out'), names=True, skip_header=1)
    xi_simple, _, _ = ng.calculateXi()
    np.testing.assert_allclose(corr2_output['gamT'], xi_simple, rtol=1.e-3)

    # Check the fits write option
    out_file_name1 = os.path.join('output','ng_out1.fits')
    ng.write(out_file_name1)
    data = fitsio.read(out_file_name1)
    np.testing.assert_almost_equal(data['R_nom'], np.exp(ng.logr))
    np.testing.assert_almost_equal(data['meanR'], ng.meanr)
    np.testing.assert_almost_equal(data['meanlogR'], ng.meanlogr)
    np.testing.assert_almost_equal(data['gamT'], ng.xi)
    np.testing.assert_almost_equal(data['gamX'], ng.xi_im)
    np.testing.assert_almost_equal(data['sigma'], np.sqrt(ng.varxi))
    np.testing.assert_almost_equal(data['weight'], ng.weight)
    np.testing.assert_almost_equal(data['npairs'], ng.npairs)

    out_file_name2 = os.path.join('output','ng_out2.fits')
    ng.write(out_file_name2, rg)
    data = fitsio.read(out_file_name2)
    np.testing.assert_almost_equal(data['R_nom'], np.exp(ng.logr))
    np.testing.assert_almost_equal(data['meanR'], ng.meanr)
    np.testing.assert_almost_equal(data['meanlogR'], ng.meanlogr)
    np.testing.assert_almost_equal(data['gamT'], xi)
    np.testing.assert_almost_equal(data['gamX'], xi_im)
    np.testing.assert_almost_equal(data['sigma'], np.sqrt(varxi))
    np.testing.assert_almost_equal(data['weight'], ng.weight)
    np.testing.assert_almost_equal(data['npairs'], ng.npairs)

    # Check the read function
    ng2 = treecorr.NGCorrelation(bin_size=0.1, min_sep=1., max_sep=20., sep_units='arcmin')
    ng2.read(out_file_name1)
    np.testing.assert_almost_equal(ng2.logr, ng.logr)
    np.testing.assert_almost_equal(ng2.meanr, ng.meanr)
    np.testing.assert_almost_equal(ng2.meanlogr, ng.meanlogr)
    np.testing.assert_almost_equal(ng2.xi, ng.xi)
    np.testing.assert_almost_equal(ng2.xi_im, ng.xi_im)
    np.testing.assert_almost_equal(ng2.varxi, ng.varxi)
    np.testing.assert_almost_equal(ng2.weight, ng.weight)
    np.testing.assert_almost_equal(ng2.npairs, ng.npairs)
    assert ng2.coords == ng.coords
    assert ng2.metric == ng.metric
    assert ng2.sep_units == ng.sep_units
    assert ng2.bin_type == ng.bin_type


def test_nmap():
    # Same scenario as above.
    # Use gamma_t(r) = gamma0 exp(-r^2/2r0^2) around a bunch of foreground lenses.
    # i.e. gamma(r) = -gamma0 exp(-r^2/2r0^2) (x+iy)^2/r^2

    # Crittenden NMap = int_0^inf gamma_t(r) T(r/R) rdr/R^2
    #                 = gamma0/4 r0^4 (r0^2 + 6R^2) / (r0^2 + 2R^2)^3

    nlens = 1000
    nsource = 10000
    gamma0 = 0.05
    r0 = 10.
    L = 50. * r0
    np.random.seed(8675309)
    xl = (np.random.random_sample(nlens)-0.5) * L
    yl = (np.random.random_sample(nlens)-0.5) * L
    xs = (np.random.random_sample(nsource)-0.5) * L
    ys = (np.random.random_sample(nsource)-0.5) * L
    g1 = np.zeros( (nsource,) )
    g2 = np.zeros( (nsource,) )
    for x,y in zip(xl,yl):
        dx = xs-x
        dy = ys-y
        r2 = dx**2 + dy**2
        gammat = gamma0 * np.exp(-0.5*r2/r0**2)
        g1 += -gammat * (dx**2-dy**2)/r2
        g2 += -gammat * (2.*dx*dy)/r2

    lens_cat = treecorr.Catalog(x=xl, y=yl, x_units='arcmin', y_units='arcmin')
    source_cat = treecorr.Catalog(x=xs, y=ys, g1=g1, g2=g2, x_units='arcmin', y_units='arcmin')
    # Measure ng with a factor of 2 extra at high and low ends
    ng = treecorr.NGCorrelation(bin_size=0.1, min_sep=0.5, max_sep=40., sep_units='arcmin',
                                verbose=1)
    ng.process(lens_cat, source_cat)

    r = ng.meanr
    true_nmap = 0.25 * gamma0 * r0**4 * (r0**2 + 6*r**2) / (r0**2 + 2*r**2)**3
    nmap, nmx, varnmap = ng.calculateNMap()

    print('nmap = ',nmap)
    print('nmx = ',nmx)
    print('true_nmap = ',true_nmap)
    mask = (1 < r) & (r < 20)
    print('ratio = ',nmap[mask] / true_nmap[mask])
    print('max rel diff = ',max(abs((nmap[mask] - true_nmap[mask])/true_nmap[mask])))
    np.testing.assert_allclose(nmap[mask], true_nmap[mask], rtol=0.1)
    np.testing.assert_allclose(nmx[mask], 0, atol=5.e-3)

    nrand = nlens * 3
    xr = (np.random.random_sample(nrand)-0.5) * L
    yr = (np.random.random_sample(nrand)-0.5) * L
    rand_cat = treecorr.Catalog(x=xr, y=yr, x_units='arcmin', y_units='arcmin')
    rg = treecorr.NGCorrelation(bin_size=0.1, min_sep=0.5, max_sep=40., sep_units='arcmin',
                                verbose=1)
    rg.process(rand_cat, source_cat)
    nmap, nmx, varnmap = ng.calculateNMap(rg, m2_uform='Crittenden')
    print('compensated nmap = ',nmap)
    print('ratio = ',nmap[mask] / true_nmap[mask])
    print('max rel diff = ',max(abs((nmap[mask] - true_nmap[mask])/true_nmap[mask])))
    np.testing.assert_allclose(nmap[mask], true_nmap[mask], rtol=0.1)
    np.testing.assert_allclose(nmx[mask], 0, atol=5.e-3)

    # Check that we get the same result using the corr2 function:
    lens_cat.write(os.path.join('data','ng_nmap_lens.dat'))
    source_cat.write(os.path.join('data','ng_nmap_source.dat'))
    rand_cat.write(os.path.join('data','ng_nmap_rand.dat'))
    config = treecorr.read_config('configs/ng_nmap.yaml')
    config['verbose'] = 0
    treecorr.corr2(config)
    corr2_output = np.genfromtxt(os.path.join('output','ng_nmap.out'), names=True)
    np.testing.assert_allclose(corr2_output['NMap'], nmap, rtol=1.e-3)
    np.testing.assert_allclose(corr2_output['NMx'], nmx, atol=1.e-3)
    np.testing.assert_allclose(corr2_output['sig_nmap'], np.sqrt(varnmap), rtol=1.e-3)

    # Can also skip the randoms (even if listed in the file)
    config['nn_statistic'] = 'simple'
    config['precision'] = 5
    treecorr.corr2(config)
    corr2_output = np.genfromtxt(os.path.join('output','ng_nmap.out'), names=True)
    np.testing.assert_allclose(corr2_output['NMap'], nmap, rtol=1.e-3)
    np.testing.assert_allclose(corr2_output['NMx'], nmx, atol=1.e-3)
    np.testing.assert_allclose(corr2_output['sig_nmap'], np.sqrt(varnmap), rtol=1.e-3)

    # And check the norm output file, which adds a few columns
    dd = treecorr.NNCorrelation(bin_size=0.1, min_sep=0.5, max_sep=40., sep_units='arcmin',
                                verbose=1)
    dd.process(lens_cat)
    rr = treecorr.NNCorrelation(bin_size=0.1, min_sep=0.5, max_sep=40., sep_units='arcmin',
                                verbose=1)
    rr.process(rand_cat)
    gg = treecorr.GGCorrelation(bin_size=0.1, min_sep=0.5, max_sep=40., sep_units='arcmin',
                                verbose=1)
    gg.process(source_cat)
    napsq, varnap = dd.calculateNapSq(rr, m2_uform='Crittenden')
    mapsq, mapsq_im, mxsq, mxsq_im, varmap = gg.calculateMapSq(m2_uform='Crittenden')
    nmap_norm = nmap**2 / napsq / mapsq
    napsq_mapsq = napsq / mapsq
    corr2_output = np.genfromtxt(os.path.join('output','ng_norm.out'), names=True)
    np.testing.assert_allclose(corr2_output['NMap'], nmap, rtol=1.e-3)
    np.testing.assert_allclose(corr2_output['NMx'], nmx, atol=1.e-3)
    np.testing.assert_allclose(corr2_output['sig_nmap'], np.sqrt(varnmap), rtol=1.e-3)
    np.testing.assert_allclose(corr2_output['Napsq'], napsq, rtol=1.e-3)
    np.testing.assert_allclose(corr2_output['sig_napsq'], np.sqrt(varnap), rtol=1.e-3)
    np.testing.assert_allclose(corr2_output['Mapsq'], mapsq, rtol=1.e-3)
    np.testing.assert_allclose(corr2_output['sig_mapsq'], np.sqrt(varmap), rtol=1.e-3)
    np.testing.assert_allclose(corr2_output['NMap_norm'], nmap_norm, rtol=1.e-3)
    np.testing.assert_allclose(corr2_output['Nsq_Mapsq'], napsq_mapsq, rtol=1.e-3)

    # Finally, let's also check the Schneider definition.
    # It doesn't have a nice closed form solution (as far as I can figure out at least).
    # but it does look qualitatively similar to the Crittenden one.
    # Just its definition of R is different, so we need to compare a different subset to
    # get a decent match.  Also, the amplitude is different by a factor of 6/5.
    nmap_sch, nmx_sch, varnmap_sch = ng.calculateNMap(rg, m2_uform='Schneider')
    print('Schneider nmap = ',nmap_sch[10:] * 5./6.)
    print('Crittenden nmap = ',nmap[:-10])
    print('ratio = ',nmap_sch[10:]*5./6. / nmap[:-10])
    np.testing.assert_allclose(nmap_sch[10:]*5./6., nmap[:-10], rtol=0.1)

    napsq_sch, varnap_sch = dd.calculateNapSq(rr, m2_uform='Schneider')
    mapsq_sch, _, mxsq_sch, _, varmap_sch = gg.calculateMapSq(m2_uform='Schneider')
    print('Schneider napsq = ',napsq_sch[10:] * 5./6.)
    print('Crittenden napsq = ',napsq[:-10])
    print('ratio = ',napsq_sch[10:]*5./6. / napsq[:-10])
    print('diff = ',napsq_sch[10:]*5./6. - napsq[:-10])

    print('Schneider mapsq = ',mapsq_sch[10:] * 5./6.)
    print('Crittenden mapsq = ',mapsq[:-10])
    print('ratio = ',mapsq_sch[10:]*5./6. / mapsq[:-10])

    # These have zero crossings, where they have slightly different shapes, so the agreement
    # isn't as good as with nmap.
    np.testing.assert_allclose(napsq_sch[10:]*5./6., napsq[:-10], rtol=0.2, atol=5.e-3)
    np.testing.assert_allclose(mapsq_sch[10:]*5./6., mapsq[:-10], rtol=0.2, atol=5.e-5)

    nmap_norm_sch = nmap_sch**2 / napsq_sch / mapsq_sch
    napsq_mapsq_sch = napsq_sch / mapsq_sch

    config['m2_uform'] = 'Schneider'
    treecorr.corr2(config)
    corr2_output = np.genfromtxt(os.path.join('output','ng_norm.out'), names=True)
    np.testing.assert_allclose(corr2_output['NMap'], nmap_sch, rtol=1.e-3)
    np.testing.assert_allclose(corr2_output['NMx'], nmx_sch, atol=1.e-3)
    np.testing.assert_allclose(corr2_output['sig_nmap'], np.sqrt(varnmap_sch), rtol=1.e-3)
    np.testing.assert_allclose(corr2_output['Napsq'], napsq_sch, rtol=1.e-3)
    np.testing.assert_allclose(corr2_output['sig_napsq'], np.sqrt(varnap_sch), rtol=1.e-3)
    np.testing.assert_allclose(corr2_output['Mapsq'], mapsq_sch, rtol=1.e-3)
    np.testing.assert_allclose(corr2_output['sig_mapsq'], np.sqrt(varmap_sch), rtol=1.e-3)
    np.testing.assert_allclose(corr2_output['NMap_norm'], nmap_norm_sch, rtol=1.e-3)
    np.testing.assert_allclose(corr2_output['Nsq_Mapsq'], napsq_mapsq_sch, rtol=1.e-3)

    with assert_raises(ValueError):
        ng.calculateNMap(m2_uform='Other')
    with assert_raises(ValueError):
        dd.calculateNapSq(rr, m2_uform='Other')
    with assert_raises(ValueError):
        gg.calculateMapSq(m2_uform='Other')


def test_pieces():
    # Test that we can do the calculation in pieces and recombine the results

    import time

    ncats = 3
    data_cats = []

    nlens = 1000
    nsource = 30000
    gamma0 = 0.05
    r0 = 10.
    L = 50. * r0
    np.random.seed(8675309)
    xl = (np.random.random_sample(nlens)-0.5) * L
    yl = (np.random.random_sample(nlens)-0.5) * L
    xs = (np.random.random_sample( (nsource,ncats) )-0.5) * L
    ys = (np.random.random_sample( (nsource,ncats) )-0.5) * L
    g1 = np.zeros( (nsource,ncats) )
    g2 = np.zeros( (nsource,ncats) )
    w = np.random.random_sample( (nsource,ncats) ) + 0.5
    for x,y in zip(xl,yl):
        dx = xs-x
        dy = ys-y
        r2 = dx**2 + dy**2
        gammat = gamma0 * np.exp(-0.5*r2/r0**2)
        g1 += -gammat * (dx**2-dy**2)/r2
        g2 += -gammat * (2.*dx*dy)/r2

    lens_cat = treecorr.Catalog(x=xl, y=yl, x_units='arcmin', y_units='arcmin')
    source_cats = [ treecorr.Catalog(x=xs[:,k], y=ys[:,k], g1=g1[:,k], g2=g2[:,k], w=w[:,k],
                                     x_units='arcmin', y_units='arcmin') for k in range(ncats) ]
    full_source_cat = treecorr.Catalog(x=xs.flatten(), y=ys.flatten(), w=w.flatten(),
                                       g1=g1.flatten(), g2=g2.flatten(),
                                       x_units='arcmin', y_units='arcmin')

    t0 = time.time()
    for k in range(ncats):
        # These could each be done on different machines in a real world application.
        ng = treecorr.NGCorrelation(bin_size=0.1, min_sep=1., max_sep=25., sep_units='arcmin',
                                    verbose=1)
        # These should use process_cross, not process, since we don't want to call finalize.
        ng.process_cross(lens_cat, source_cats[k])
        ng.write(os.path.join('output','ng_piece_%d.fits'%k))

    pieces_ng = treecorr.NGCorrelation(bin_size=0.1, min_sep=1., max_sep=25., sep_units='arcmin')
    for k in range(ncats):
        ng = pieces_ng.copy()
        ng.read(os.path.join('output','ng_piece_%d.fits'%k))
        pieces_ng += ng
    varg = treecorr.calculateVarG(source_cats)
    pieces_ng.finalize(varg)
    t1 = time.time()
    print ('time for piece-wise processing (including I/O) = ',t1-t0)

    full_ng = treecorr.NGCorrelation(bin_size=0.1, min_sep=1., max_sep=25., sep_units='arcmin',
                                     verbose=1)
    full_ng.process(lens_cat, full_source_cat)
    t2 = time.time()
    print ('time for full processing = ',t2-t1)

    print('max error in meanr = ',np.max(pieces_ng.meanr - full_ng.meanr),)
    print('    max meanr = ',np.max(full_ng.meanr))
    print('max error in meanlogr = ',np.max(pieces_ng.meanlogr - full_ng.meanlogr),)
    print('    max meanlogr = ',np.max(full_ng.meanlogr))
    print('max error in npairs = ',np.max(pieces_ng.npairs - full_ng.npairs),)
    print('    max npairs = ',np.max(full_ng.npairs))
    print('max error in weight = ',np.max(pieces_ng.weight - full_ng.weight),)
    print('    max weight = ',np.max(full_ng.weight))
    print('max error in xi = ',np.max(pieces_ng.xi - full_ng.xi),)
    print('    max xi = ',np.max(full_ng.xi))
    print('max error in xi_im = ',np.max(pieces_ng.xi_im - full_ng.xi_im),)
    print('    max xi_im = ',np.max(full_ng.xi_im))
    print('max error in varxi = ',np.max(pieces_ng.varxi - full_ng.varxi),)
    print('    max varxi = ',np.max(full_ng.varxi))
    np.testing.assert_allclose(pieces_ng.meanr, full_ng.meanr, rtol=2.e-3)
    np.testing.assert_allclose(pieces_ng.meanlogr, full_ng.meanlogr, atol=2.e-3)
    np.testing.assert_allclose(pieces_ng.npairs, full_ng.npairs, rtol=3.e-2)
    np.testing.assert_allclose(pieces_ng.weight, full_ng.weight, rtol=3.e-2)
    np.testing.assert_allclose(pieces_ng.xi, full_ng.xi, rtol=0.1)
    np.testing.assert_allclose(pieces_ng.xi_im, full_ng.xi_im, atol=2.e-3)
    np.testing.assert_allclose(pieces_ng.varxi, full_ng.varxi, rtol=3.e-2)

    # A different way to do this can produce results that are essentially identical to the
    # full calculation.  We can use wpos = w, but set w = 0 for the items in the pieces catalogs
    # that we don't want to include.  This will force the tree to be built identically in each
    # case, but only use the subset of items in the calculation.  The sum of all these should
    # be identical to the full calculation aside from order of calculation differences.
    # However, we lose some to speed, since there are a lot more wasted calculations along the
    # way that have to be duplicated in each piece.
    w2 = [ np.empty(w.shape) for k in range(ncats) ]
    for k in range(ncats):
        w2[k][:,:] = 0.
        w2[k][:,k] = w[:,k]
    source_cats2 = [ treecorr.Catalog(x=xs.flatten(), y=ys.flatten(),
                                      g1=g1.flatten(), g2=g2.flatten(),
                                      wpos=w.flatten(), w=w2[k].flatten(),
                                      x_units='arcmin', y_units='arcmin') for k in range(ncats) ]

    t3 = time.time()
    ng2 = [ full_ng.copy() for k in range(ncats) ]
    for k in range(ncats):
        ng2[k].clear()
        ng2[k].process_cross(lens_cat, source_cats2[k])

    pieces_ng2 = full_ng.copy()
    pieces_ng2.clear()
    for k in range(ncats):
        pieces_ng2 += ng2[k]
    pieces_ng2.finalize(varg)
    t4 = time.time()
    print ('time for zero-weight piece-wise processing = ',t4-t3)

    print('max error in meanr = ',np.max(pieces_ng2.meanr - full_ng.meanr),)
    print('    max meanr = ',np.max(full_ng.meanr))
    print('max error in meanlogr = ',np.max(pieces_ng2.meanlogr - full_ng.meanlogr),)
    print('    max meanlogr = ',np.max(full_ng.meanlogr))
    print('max error in npairs = ',np.max(pieces_ng2.npairs - full_ng.npairs),)
    print('    max npairs = ',np.max(full_ng.npairs))
    print('max error in weight = ',np.max(pieces_ng2.weight - full_ng.weight),)
    print('    max weight = ',np.max(full_ng.weight))
    print('max error in xi = ',np.max(pieces_ng2.xi - full_ng.xi),)
    print('    max xi = ',np.max(full_ng.xi))
    print('max error in xi_im = ',np.max(pieces_ng2.xi_im - full_ng.xi_im),)
    print('    max xi_im = ',np.max(full_ng.xi_im))
    print('max error in varxi = ',np.max(pieces_ng2.varxi - full_ng.varxi),)
    print('    max varxi = ',np.max(full_ng.varxi))
    np.testing.assert_allclose(pieces_ng2.meanr, full_ng.meanr, rtol=1.e-7)
    np.testing.assert_allclose(pieces_ng2.meanlogr, full_ng.meanlogr, rtol=1.e-7)
    np.testing.assert_allclose(pieces_ng2.npairs, full_ng.npairs, rtol=1.e-7)
    np.testing.assert_allclose(pieces_ng2.weight, full_ng.weight, rtol=1.e-7)
    np.testing.assert_allclose(pieces_ng2.xi, full_ng.xi, rtol=1.e-7)
    np.testing.assert_allclose(pieces_ng2.xi_im, full_ng.xi_im, atol=1.e-10)
    np.testing.assert_allclose(pieces_ng2.varxi, full_ng.varxi, rtol=1.e-7)

    # Try this with corr2
    lens_cat.write(os.path.join('data','ng_wpos_lens.fits'))
    for i, sc in enumerate(source_cats2):
        sc.write(os.path.join('data','ng_wpos_source%d.fits'%i))
    config = treecorr.read_config('configs/ng_wpos.yaml')
    config['verbose'] = 0
    treecorr.corr2(config)
    data = fitsio.read(config['ng_file_name'])
    print('data.dtype = ',data.dtype)
    np.testing.assert_allclose(data['meanR'], full_ng.meanr, rtol=1.e-7)
    np.testing.assert_allclose(data['meanlogR'], full_ng.meanlogr, rtol=1.e-7)
    np.testing.assert_allclose(data['npairs'], full_ng.npairs, rtol=1.e-7)
    np.testing.assert_allclose(data['weight'], full_ng.weight, rtol=1.e-7)
    np.testing.assert_allclose(data['gamT'], full_ng.xi, rtol=1.e-7)
    np.testing.assert_allclose(data['gamX'], full_ng.xi_im, atol=1.e-10)
    np.testing.assert_allclose(data['sigma']**2, full_ng.varxi, rtol=1.e-7)


def test_rlens():
    # Same as above, except use R_lens for separation.
    # Use gamma_t(r) = gamma0 exp(-R^2/2R0^2) around a bunch of foreground lenses.

    nlens = 100
    nsource = 200000
    gamma0 = 0.05
    R0 = 10.
    L = 50. * R0
    np.random.seed(8675309)
    xl = (np.random.random_sample(nlens)-0.5) * L  # -250 < x < 250
    zl = (np.random.random_sample(nlens)-0.5) * L  # -250 < y < 250
    yl = np.random.random_sample(nlens) * 4*L + 10*L  # 5000 < z < 7000
    rl = np.sqrt(xl**2 + yl**2 + zl**2)
    xs = (np.random.random_sample(nsource)-0.5) * L
    zs = (np.random.random_sample(nsource)-0.5) * L
    ys = np.random.random_sample(nsource) * 8*L + 160*L  # 80000 < z < 84000
    rs = np.sqrt(xs**2 + ys**2 + zs**2)
    g1 = np.zeros( (nsource,) )
    g2 = np.zeros( (nsource,) )
    bin_size = 0.1
    # min_sep is set so the first bin doesn't have 0 pairs.
    min_sep = 1.3*R0
    # max_sep can't be too large, since the measured value starts to have shape noise for larger
    # values of separation.  We're not adding any shape noise directly, but the shear from other
    # lenses is effectively a shape noise, and that comes to dominate the measurement above ~4R0.
    max_sep = 3.5*R0
    nbins = int(np.ceil(np.log(max_sep/min_sep)/bin_size))
    true_gt = np.zeros( (nbins,) )
    true_npairs = np.zeros((nbins,), dtype=int)
    print('Making shear vectors')
    for x,y,z,r in zip(xl,yl,zl,rl):
        # Rlens = |r1 x r2| / |r2|
        xcross = ys * z - zs * y
        ycross = zs * x - xs * z
        zcross = xs * y - ys * x
        Rlens = np.sqrt(xcross**2 + ycross**2 + zcross**2) / rs

        gammat = gamma0 * np.exp(-0.5*Rlens**2/R0**2)
        # For the rotation, approximate that the x,z coords are approx the perpendicular plane.
        # So just normalize back to the unit sphere and do the 2d projection calculation.
        # It's not exactly right, but it should be good enough for this unit test.
        dx = xs/rs-x/r
        dz = zs/rs-z/r
        drsq = dx**2 + dz**2
        g1 += -gammat * (dx**2-dz**2)/drsq
        g2 += -gammat * (2.*dx*dz)/drsq
        index = np.floor( np.log(Rlens/min_sep) / bin_size).astype(int)
        mask = (index >= 0) & (index < nbins)
        np.add.at(true_gt, index[mask], gammat[mask])
        np.add.at(true_npairs, index[mask], 1)
    true_gt /= true_npairs

    # Start with bin_slop == 0.  With only 100 lenses, this still runs very fast.
    lens_cat = treecorr.Catalog(x=xl, y=yl, z=zl)
    source_cat = treecorr.Catalog(x=xs, y=ys, z=zs, g1=g1, g2=g2)
    ng0 = treecorr.NGCorrelation(bin_size=bin_size, min_sep=min_sep, max_sep=max_sep, verbose=1,
                                 metric='Rlens', bin_slop=0)
    ng0.process(lens_cat, source_cat)

    Rlens = ng0.meanr
    theory_gt = gamma0 * np.exp(-0.5*Rlens**2/R0**2)

    print('Results with bin_slop = 0:')
    print('ng.npairs = ',ng0.npairs)
    print('true_npairs = ',true_npairs)
    print('ng.xi = ',ng0.xi)
    print('true_gammat = ',true_gt)
    print('ratio = ',ng0.xi / true_gt)
    print('diff = ',ng0.xi - true_gt)
    print('max diff = ',max(abs(ng0.xi - true_gt)))
    print('ng.xi_im = ',ng0.xi_im)
    np.testing.assert_allclose(ng0.xi, true_gt, rtol=1.e-3)
    np.testing.assert_allclose(ng0.xi_im, 0, atol=1.e-6)

    print('ng.xi = ',ng0.xi)
    print('theory_gammat = ',theory_gt)
    print('ratio = ',ng0.xi / theory_gt)
    print('diff = ',ng0.xi - theory_gt)
    print('max diff = ',max(abs(ng0.xi - theory_gt)))
    np.testing.assert_allclose(ng0.xi, theory_gt, rtol=0.1)

    # Now use a more normal value for bin_slop.
    ng1 = treecorr.NGCorrelation(bin_size=bin_size, min_sep=min_sep, max_sep=max_sep, verbose=1,
                                 metric='Rlens', bin_slop=0.5)
    ng1.process(lens_cat, source_cat)
    Rlens = ng1.meanr
    theory_gt = gamma0 * np.exp(-0.5*Rlens**2/R0**2)

    print('Results with bin_slop = 0.5')
    print('ng.npairs = ',ng1.npairs)
    print('ng.xi = ',ng1.xi)
    print('theory_gammat = ',theory_gt)
    print('ratio = ',ng1.xi / theory_gt)
    print('diff = ',ng1.xi - theory_gt)
    print('max diff = ',max(abs(ng1.xi - theory_gt)))
    print('ng.xi_im = ',ng1.xi_im)
    np.testing.assert_allclose(ng1.xi, true_gt, rtol=0.02)
    np.testing.assert_allclose(ng1.xi_im, 0, atol=1.e-4)

    # Check that we get the same result using the corr2 function:
    lens_cat.write(os.path.join('data','ng_rlens_lens.dat'))
    source_cat.write(os.path.join('data','ng_rlens_source.dat'))
    config = treecorr.read_config('configs/ng_rlens.yaml')
    config['verbose'] = 0
    treecorr.corr2(config)
    corr2_output = np.genfromtxt(os.path.join('output','ng_rlens.out'), names=True,
                                    skip_header=1)
    print('ng.xi = ',ng1.xi)
    print('from corr2 output = ',corr2_output['gamT'])
    print('ratio = ',corr2_output['gamT']/ng1.xi)
    print('diff = ',corr2_output['gamT']-ng1.xi)
    np.testing.assert_allclose(corr2_output['gamT'], ng1.xi, rtol=1.e-3)
    np.testing.assert_allclose(corr2_output['gamX'], ng1.xi_im, rtol=1.e-3)

    # Repeat with the sources being given as RA/Dec only.
    ral, decl = coord.CelestialCoord.xyz_to_radec(xl,yl,zl)
    ras, decs = coord.CelestialCoord.xyz_to_radec(xs,ys,zs)
    lens_cat = treecorr.Catalog(ra=ral, dec=decl, ra_units='radians', dec_units='radians', r=rl)
    source_cat = treecorr.Catalog(ra=ras, dec=decs, ra_units='radians', dec_units='radians',
                                  g1=g1, g2=g2)

    # Again, start with bin_slop == 0.
    # This version should be identical to the 3D version.  When bin_slop != 0, it won't be
    # exactly identical, since the tree construction will have different decisions along the
    # way (since everything is at the same radius here), but the results are consistent.
    ng0s = treecorr.NGCorrelation(bin_size=bin_size, min_sep=min_sep, max_sep=max_sep, verbose=1,
                                  metric='Rlens', bin_slop=0)
    ng0s.process(lens_cat, source_cat)

    Rlens = ng0s.meanr
    theory_gt = gamma0 * np.exp(-0.5*Rlens**2/R0**2)

    print('Results when sources have no radius information, first bin_slop=0')
    print('ng.npairs = ',ng0s.npairs)
    print('true_npairs = ',true_npairs)
    print('ng.xi = ',ng0s.xi)
    print('true_gammat = ',true_gt)
    print('ratio = ',ng0s.xi / true_gt)
    print('diff = ',ng0s.xi - true_gt)
    print('max diff = ',max(abs(ng0s.xi - true_gt)))
    print('ng.xi_im = ',ng0s.xi_im)
    np.testing.assert_allclose(ng0s.xi, true_gt, rtol=1.e-4)
    np.testing.assert_allclose(ng0s.xi_im, 0, atol=1.e-5)

    print('ng.xi = ',ng0s.xi)
    print('theory_gammat = ',theory_gt)
    print('ratio = ',ng0s.xi / theory_gt)
    print('diff = ',ng0s.xi - theory_gt)
    print('max diff = ',max(abs(ng0s.xi - theory_gt)))
    np.testing.assert_allclose(ng0s.xi, theory_gt, rtol=0.05)

    np.testing.assert_allclose(ng0s.xi, ng0.xi, rtol=1.e-6)
    np.testing.assert_allclose(ng0s.xi_im, 0, atol=1.e-6)
    np.testing.assert_allclose(ng0s.npairs, ng0.npairs, atol=1.e-6)

    # Now use a more normal value for bin_slop.
    ng1s = treecorr.NGCorrelation(bin_size=bin_size, min_sep=min_sep, max_sep=max_sep, verbose=1,
                                  metric='Rlens', bin_slop=0.3)
    ng1s.process(lens_cat, source_cat)
    Rlens = ng1s.meanr
    theory_gt = gamma0 * np.exp(-0.5*Rlens**2/R0**2)

    print('Results with bin_slop = 0.5')
    print('ng.npairs = ',ng1s.npairs)
    print('ng.xi = ',ng1s.xi)
    print('theory_gammat = ',theory_gt)
    print('ratio = ',ng1s.xi / theory_gt)
    print('diff = ',ng1s.xi - theory_gt)
    print('max diff = ',max(abs(ng1s.xi - theory_gt)))
    print('ng.xi_im = ',ng1s.xi_im)
    np.testing.assert_allclose(ng1s.xi, theory_gt, rtol=0.1)
    np.testing.assert_allclose(ng1s.xi_im, 0, atol=1.e-5)


def test_rlens_bkg():
    # Same as above, except limit the sources to be in the background of the lens.

    nlens = 100
    nsource = 100000
    gamma0 = 0.05
    R0 = 10.
    L = 50. * R0
    np.random.seed(8675309)
    xl = (np.random.random_sample(nlens)-0.5) * L  # -250 < x < 250
    zl = (np.random.random_sample(nlens)-0.5) * L  # -250 < y < 250
    yl = np.random.random_sample(nlens) * 4*L + 10*L  # 5000 < z < 7000
    rl = np.sqrt(xl**2 + yl**2 + zl**2)
    xs = (np.random.random_sample(nsource)-0.5) * L
    zs = (np.random.random_sample(nsource)-0.5) * L
    ys = np.random.random_sample(nsource) * 12*L + 8*L  # 4000 < z < 10000
    rs = np.sqrt(xs**2 + ys**2 + zs**2)
    print('xl = ',np.min(xl),np.max(xl))
    print('yl = ',np.min(yl),np.max(yl))
    print('zl = ',np.min(zl),np.max(zl))
    print('xs = ',np.min(xs),np.max(xs))
    print('ys = ',np.min(ys),np.max(ys))
    print('zs = ',np.min(zs),np.max(zs))
    g1 = np.zeros( (nsource,) )
    g2 = np.zeros( (nsource,) )
    bin_size = 0.1
    # min_sep is set so the first bin doesn't have 0 pairs.
    min_sep = 1.3*R0
    # max_sep can't be too large, since the measured value starts to have shape noise for larger
    # values of separation.  We're not adding any shape noise directly, but the shear from other
    # lenses is effectively a shape noise, and that comes to dominate the measurement above ~4R0.
    max_sep = 2.5*R0
    nbins = int(np.ceil(np.log(max_sep/min_sep)/bin_size))
    print('Making shear vectors')
    for x,y,z,r in zip(xl,yl,zl,rl):
        # This time, only give the true shear to the background galaxies.
        bkg = (rs > r)

        # Rlens = |r1 x r2| / |r2|
        xcross = ys[bkg] * z - zs[bkg] * y
        ycross = zs[bkg] * x - xs[bkg] * z
        zcross = xs[bkg] * y - ys[bkg] * x
        Rlens = np.sqrt(xcross**2 + ycross**2 + zcross**2) / (rs[bkg])

        gammat = gamma0 * np.exp(-0.5*Rlens**2/R0**2)
        # For the rotation, approximate that the x,z coords are approx the perpendicular plane.
        # So just normalize back to the unit sphere and do the 2d projection calculation.
        # It's not exactly right, but it should be good enough for this unit test.
        dx = (xs/rs)[bkg]-x/r
        dz = (zs/rs)[bkg]-z/r
        drsq = dx**2 + dz**2

        g1[bkg] += -gammat * (dx**2-dz**2)/drsq
        g2[bkg] += -gammat * (2.*dx*dz)/drsq

    # Slight subtlety in this test vs the previous one.  We need to build up the full g1,g2
    # arrays first before calculating the true_gt value, since we need to include the background
    # galaxies for each lens regardless of whether they had signal or not.
    true_gt = np.zeros( (nbins,) )
    true_npairs = np.zeros((nbins,), dtype=int)
    # Along the way, do the same test for Arc metric.
    min_sep_arc = 10   # arcmin
    max_sep_arc = 200
    min_sep_arc_rad = min_sep_arc * coord.arcmin / coord.radians
    nbins_arc = int(np.ceil(np.log(max_sep_arc/min_sep_arc)/bin_size))
    true_gt_arc = np.zeros( (nbins_arc,) )
    true_npairs_arc = np.zeros((nbins_arc,), dtype=int)
    for x,y,z,r in zip(xl,yl,zl,rl):
        # Rlens = |r1 x r2| / |r2|
        xcross = ys * z - zs * y
        ycross = zs * x - xs * z
        zcross = xs * y - ys * x
        Rlens = np.sqrt(xcross**2 + ycross**2 + zcross**2) / rs
        dx = xs/rs-x/r
        dz = zs/rs-z/r
        drsq = dx**2 + dz**2
        gt = -g1 * (dx**2-dz**2)/drsq - g2 * (2.*dx*dz)/drsq
        bkg = (rs > r)
        index = np.floor( np.log(Rlens/min_sep) / bin_size).astype(int)
        mask = (index >= 0) & (index < nbins) & bkg
        np.add.at(true_gt, index[mask], gt[mask])
        np.add.at(true_npairs, index[mask], 1)

        # Arc bins by theta, which is arcsin(Rlens / r)
        theta = np.arcsin(Rlens / r)
        index = np.floor( np.log(theta / min_sep_arc_rad) / bin_size).astype(int)
        mask = (index >= 0) & (index < nbins_arc) & bkg
        np.add.at(true_gt_arc, index[mask], gt[mask])
        np.add.at(true_npairs_arc, index[mask], 1)

    true_gt /= true_npairs
    true_gt_arc /= true_npairs_arc

    # Start with bin_slop == 0.  With only 100 lenses, this still runs very fast.
    lens_cat = treecorr.Catalog(x=xl, y=yl, z=zl)
    source_cat = treecorr.Catalog(x=xs, y=ys, z=zs, g1=g1, g2=g2)
    ng0 = treecorr.NGCorrelation(bin_size=bin_size, min_sep=min_sep, max_sep=max_sep, verbose=1,
                                 metric='Rlens', bin_slop=0, min_rpar=0)
    ng0.process(lens_cat, source_cat)

    Rlens = ng0.meanr
    theory_gt = gamma0 * np.exp(-0.5*Rlens**2/R0**2)

    print('Results with bin_slop = 0:')
    print('ng.npairs = ',ng0.npairs)
    print('true_npairs = ',true_npairs)
    print('ng.xi = ',ng0.xi)
    print('true_gammat = ',true_gt)
    print('ratio = ',ng0.xi / true_gt)
    print('diff = ',ng0.xi - true_gt)
    print('max diff = ',max(abs(ng0.xi - true_gt)))
    np.testing.assert_allclose(ng0.xi, true_gt, rtol=1.e-3)

    print('ng.xi = ',ng0.xi)
    print('theory_gammat = ',theory_gt)
    print('ratio = ',ng0.xi / theory_gt)
    print('diff = ',ng0.xi - theory_gt)
    print('max diff = ',max(abs(ng0.xi - theory_gt)))
    print('ng.xi_im = ',ng0.xi_im)
    np.testing.assert_allclose(ng0.xi, theory_gt, rtol=0.5)
    np.testing.assert_allclose(ng0.xi, theory_gt, atol=1.e-3)
    np.testing.assert_allclose(ng0.xi_im, 0, atol=1.e-3)

    # Without min_rpar, this should fail.
    lens_cat = treecorr.Catalog(x=xl, y=yl, z=zl)
    source_cat = treecorr.Catalog(x=xs, y=ys, z=zs, g1=g1, g2=g2)
    ng0 = treecorr.NGCorrelation(bin_size=bin_size, min_sep=min_sep, max_sep=max_sep, verbose=1,
                                 metric='Rlens', bin_slop=0)
    ng0.process(lens_cat, source_cat)
    Rlens = ng0.meanr

    print('Results without min_rpar')
    print('ng.xi = ',ng0.xi)
    print('true_gammat = ',true_gt)
    print('max diff = ',max(abs(ng0.xi - true_gt)))
    assert max(abs(ng0.xi - true_gt)) > 5.e-3

    # Now use a more normal value for bin_slop.
    ng1 = treecorr.NGCorrelation(bin_size=bin_size, min_sep=min_sep, max_sep=max_sep, verbose=1,
                                 metric='Rlens', bin_slop=0.5, min_rpar=0)
    ng1.process(lens_cat, source_cat)
    Rlens = ng1.meanr
    theory_gt = gamma0 * np.exp(-0.5*Rlens**2/R0**2)

    print('Results with bin_slop = 0.5')
    print('ng.npairs = ',ng1.npairs)
    print('ng.xi = ',ng1.xi)
    print('theory_gammat = ',theory_gt)
    print('ratio = ',ng1.xi / theory_gt)
    print('diff = ',ng1.xi - theory_gt)
    print('max diff = ',max(abs(ng1.xi - theory_gt)))
    print('ng.xi_im = ',ng1.xi_im)
    np.testing.assert_allclose(ng1.xi, theory_gt, rtol=0.5)
    np.testing.assert_allclose(ng1.xi, theory_gt, atol=1.e-3)
    np.testing.assert_allclose(ng1.xi_im, 0, atol=1.e-3)

    # Check that we get the same result using the corr2 function:
    lens_cat.write(os.path.join('data','ng_rlens_bkg_lens.dat'))
    source_cat.write(os.path.join('data','ng_rlens_bkg_source.dat'))
    config = treecorr.read_config('configs/ng_rlens_bkg.yaml')
    config['verbose'] = 0
    treecorr.corr2(config)
    corr2_output = np.genfromtxt(os.path.join('output','ng_rlens_bkg.out'), names=True,
                                    skip_header=1)
    print('ng.xi = ',ng1.xi)
    print('from corr2 output = ',corr2_output['gamT'])
    print('ratio = ',corr2_output['gamT']/ng1.xi)
    print('diff = ',corr2_output['gamT']-ng1.xi)
    np.testing.assert_allclose(corr2_output['gamT'], ng1.xi, rtol=1.e-3)
    np.testing.assert_allclose(corr2_output['gamX'], ng1.xi_im, atol=1.e-3)

    # Repeat with Arc metric
    ng2 = treecorr.NGCorrelation(bin_size=bin_size, min_sep=min_sep_arc, max_sep=max_sep_arc,
                                 metric='Arc', bin_slop=0, min_rpar=0, sep_units='arcmin')
    ng2.process(lens_cat, source_cat)

    print('Results with bin_slop = 0:')
    print('ng.npairs = ',ng2.npairs)
    print('true_npairs = ',true_npairs_arc)
    print('ng.xi = ',ng2.xi)
    print('true_gammat = ',true_gt_arc)
    print('ratio = ',ng2.xi / true_gt_arc)
    print('diff = ',ng2.xi - true_gt_arc)
    print('max diff = ',max(abs(ng2.xi - true_gt_arc)))
    np.testing.assert_allclose(ng2.xi, true_gt_arc, rtol=5.e-3)
    np.testing.assert_allclose(ng2.xi_im, 0, atol=5.e-4)

    # Without min_rpar, this should fail.
    lens_cat = treecorr.Catalog(x=xl, y=yl, z=zl)
    source_cat = treecorr.Catalog(x=xs, y=ys, z=zs, g1=g1, g2=g2)
    ng2 = treecorr.NGCorrelation(bin_size=bin_size, min_sep=min_sep_arc, max_sep=max_sep_arc,
                                 metric='Arc', bin_slop=0, sep_units='arcmin')
    ng2.process(lens_cat, source_cat)
    Rlens = ng2.meanr

    print('Results without min_rpar')
    print('ng.xi = ',ng2.xi)
    print('true_gammat = ',true_gt_arc)
    print('max diff = ',max(abs(ng2.xi - true_gt_arc)))
    assert max(abs(ng2.xi - true_gt_arc)) > 2.e-3

    # Now use a more normal value for bin_slop.
    ng3 = treecorr.NGCorrelation(bin_size=bin_size, min_sep=min_sep_arc, max_sep=max_sep_arc,
                                 metric='Arc', bin_slop=0.5, min_rpar=0, sep_units='arcmin')
    ng3.process(lens_cat, source_cat)

    print('Results with bin_slop = 0.5')
    print('ng.npairs = ',ng3.npairs)
    print('ng.xi = ',ng3.xi)
    print('ng.xi_im = ',ng3.xi_im)
    np.testing.assert_allclose(ng3.xi, true_gt_arc, rtol=1.e-2)
    np.testing.assert_allclose(ng3.xi_im, 0, atol=1.e-3)


def test_haloellip():
    """This is similar to the Clampitt halo ellipticity measurement, but using counts for the
    background galaxies rather than shears.

    w_aligned = Sum_i (w_i * cos(2theta)) / Sum_i (w_i)
    w_cross = Sum_i (w_i * sin(2theta)) / Sum_i (w_i)

    where theta is measured w.r.t. the coordinate system where the halo ellitpicity
    is along the x-axis.  Converting this to complex notation, we obtain:

    w_a - i w_c = < exp(-2itheta) >
                = < exp(2iphi) exp(-2i(theta+phi)) >
                = < ehalo exp(-2i(theta+phi)) >

    where ehalo = exp(2iphi) is the unit-normalized shape of the halo in the normal world
    coordinate system.  Note that the combination theta+phi is the angle between the line joining
    the two points and the E-W coordinate, which means that

    w_a - i w_c = -gamma_t(n_bg, ehalo)

    so the reverse of the usual galaxy-galaxy lensing order.  The N is the background galaxies
    and G is the halo shapes (normalized to have |ehalo| = 1).
    """

    nhalo = 10
    nsource = 100000  # sources per halo
    ntot = nsource * nhalo
    L = 100000.  # The side length in which the halos are placed
    R = 10.      # The (rms) radius of the associated sources from the halos
                 # In this case, we want L >> R so that most sources are only associated
                 # with the one halo we used for assigning its shear value.

    # Lenses are randomly located with random shapes.
    np.random.seed(86753099)
    halo_g1 = np.random.normal(0., 0.3, (nhalo,))
    halo_g2 = np.random.normal(0., 0.3, (nhalo,))
    halo_g = halo_g1 + 1j * halo_g2
    # The interpretation is simpler if they all have the same |g|, so just make them all 0.3.
    halo_g *= 0.3 / np.abs(halo_g)
    halo_absg = np.abs(halo_g)
    halo_x = (np.random.random_sample(nhalo)-0.5) * L
    halo_y = (np.random.random_sample(nhalo)-0.5) * L
    print('Made halos',len(halo_x))

    # For the sources, place nsource galaxies around each halo with the expected azimuthal pattern
    source_x = np.empty(ntot)
    source_y = np.empty(ntot)
    for i in range(nhalo):
        absg = halo_absg[i]
        # First position the sources in a Gaussian cloud around the halo center.
        dx = np.random.normal(0., 10., (nsource,))
        dy = np.random.normal(0., 10., (nsource,))
        r = np.sqrt(dx*dx + dy*dy)
        t = np.arctan2(dy,dx)
        # z = dx + idy = r exp(it)

        # Reposition the sources azimuthally so p(theta) ~ 1 + |g_halo| * cos(2 theta)
        # Currently t has p(t) = 1/2pi.
        # Let u be the new azimuthal angle with p(u) = (1/2pi) (1 + |g| cos(2u))
        # p(u) = |dt/du| p(t)
        # 1 + |g| cos(2u) = dt/du
        # t = int( (1 + |g| cos(2u)) du = u + 1/2 |g| sin(2u)

        # This doesn't have an analytic solution, but a few iterations of Newton-Raphson
        # should work well enough.
        u = t.copy()
        for k in range(4):
            u -= (u - t + 0.5 * absg * np.sin(2.*u)) / (1. + absg * np.cos(2.*u))

        z = r * np.exp(1j * u)
        exp2iphi = z**2 / np.abs(z)**2

        # Now rotate the whole system by the phase of the halo ellipticity.
        exp2ialpha = halo_g[i] / absg
        expialpha = np.sqrt(exp2ialpha)
        z *= expialpha
        # Place the source galaxies at this dx,dy with this shape
        source_x[i*nsource: (i+1)*nsource] = halo_x[i] + z.real
        source_y[i*nsource: (i+1)*nsource] = halo_y[i] + z.imag
    print('Made sources',len(source_x))

    source_cat = treecorr.Catalog(x=source_x, y=source_y)
    # Big fat bin to increase S/N.  The way I set it up, the signal is the same in all
    # radial bins, so just combine them together for higher S/N.
    ng = treecorr.NGCorrelation(min_sep=5, max_sep=10, nbins=1)
    halo_mean_absg = np.mean(halo_absg)
    print('mean_absg = ',halo_mean_absg)

    # First the original version where we only use the phase of the halo ellipticities:
    halo_cat1 = treecorr.Catalog(x=halo_x, y=halo_y,
                                 g1=halo_g.real/halo_absg, g2=halo_g.imag/halo_absg)
    ng.process(source_cat, halo_cat1)
    print('ng.npairs = ',ng.npairs)
    print('ng.xi = ',ng.xi)
    # The expected signal is
    # E(ng) = - < int( p(t) cos(2t) ) >
    #       = - < int( (1 + e_halo cos(2t)) cos(2t) ) >
    #       = -0.5 <e_halo>
    print('expected signal = ',-0.5 * halo_mean_absg)
    np.testing.assert_allclose(ng.xi, -0.5 * halo_mean_absg, rtol=0.05)

    # Next weight the halos by their absg.
    halo_cat2 = treecorr.Catalog(x=halo_x, y=halo_y, w=halo_absg,
                                 g1=halo_g.real/halo_absg, g2=halo_g.imag/halo_absg)
    ng.process(source_cat, halo_cat2)
    print('ng.xi = ',ng.xi)
    # Now the net signal is
    # sum(w * p*cos(2t)) / sum(w)
    # = 0.5 * <absg^2> / <absg>
    halo_mean_gsq = np.mean(halo_absg**2)
    print('expected signal = ',0.5 * halo_mean_gsq / halo_mean_absg)
    np.testing.assert_allclose(ng.xi, -0.5 * halo_mean_gsq / halo_mean_absg, rtol=0.05)

    # Finally, use the unnormalized halo_g for the halo ellipticities
    halo_cat3 = treecorr.Catalog(x=halo_x, y=halo_y, g1=halo_g.real, g2=halo_g.imag)
    ng.process(source_cat, halo_cat3)
    print('ng.xi = ',ng.xi)
    # Now the net signal is
    # sum(absg * p*cos(2t)) / N
    # = 0.5 * <absg^2>
    print('expected signal = ',0.5 * halo_mean_gsq)
    np.testing.assert_allclose(ng.xi, -0.5 * halo_mean_gsq, rtol=0.05)


if __name__ == '__main__':
    test_single()
    test_pairwise()
    test_spherical()
    test_ng()
    test_pieces()
    test_rlens()
    test_rlens_bkg()
    test_haloellip()
