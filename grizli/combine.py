"""
Combine FLTs at the same orientation
"""
import copy
import glob

import numpy as np

import astropy.wcs as pywcs
import astropy.io.fits as pyfits

from drizzlepac import astrodrizzle

from . import utils
from . import assoc

def consolodate_grism_lists(gs_direct):
    """TBD
    
    Combine visits of same target at same angle
    """
    
def combine_filter_combinations(root='udf', grow=2, ds9=None, verbose=True,
                                clobber=True, filters=['G102', 'G141']):
    """TBD
    """
    files=glob.glob('i*flt.fits')
    output_list, filter_list = utils.parse_flt_files(files, uniquename=False)
    
    for filt in filter_list.keys():
        if filt in filters:
            for angle in filter_list[filt]:
                output = '%s-%05.1f-%s_cmb.fits' %(root, angle, filt)
                if verbose:
                    print '\n -- Combine: %s -- \n' %(output)
                    
                combine_flt(files=filter_list[filt][angle], output=output, 
                            grow=grow, ds9=ds9, verbose=verbose, 
                            clobber=clobber)

def combine_visit_combinations(grow=2, ds9=None, verbose=True,
                               clobber=True, pixfrac=0.5, kernel='point', 
                               filters=['G102', 'G141'], skip=1):
    """TBD
    """
    files=glob.glob('i*flt.fits')
    output_list, filter_list = utils.parse_flt_files(files, uniquename=False)
    
    for key in output_list.keys()[::skip]:
        filter=key.split('-')[-1].upper()
        if filter not in filters:
            continue
        
        output = '%s_cmb.fits' %(key)

        if verbose:
            print '\n -- Combine: %s -- \n' %(output)
            
        combine_flt(files=output_list[key], output=output, 
                    grow=grow, ds9=ds9, verbose=verbose, 
                    clobber=clobber, pixfrac=pixfrac, kernel=kernel)

def get_shifts(files, ref_pixel=[507, 507]):
    """
    TBD
    """
    f0 = pyfits.open(files[0])
    h0 = f0[0].header.copy()
    h0['EXPTIME'] = 0.
    
    out_wcs = pywcs.WCS(f0[1].header, relax=True)
    out_wcs.pscale = utils.get_wcs_pscale(out_wcs)
    
    ### Offsets
    ra0, de0 = out_wcs.all_pix2world([ref_pixel[0]],[ref_pixel[1]],0)

    x0 = np.zeros(len(files))
    y0 = np.zeros(len(files))

    for i, file in enumerate(files):
        hx = pyfits.getheader(file, 0)
        h0['EXPTIME'] += hx['EXPTIME']
        h0['FILE%04d' %(i)] = file, 'Included file #%d' %(i)
    
        h = pyfits.getheader(file, 1)
        flt_wcs = pywcs.WCS(h, relax=True)
        x0[i], y0[i] = flt_wcs.all_world2pix(ra0, de0, 0)

    return h0, x0-ref_pixel[0], y0-ref_pixel[1]

def split_pixel_quadrant(dx, dy):
    """
    TBD
    
    Group offsets by the quadrant they put the central pixel in
    """
    xq = np.cast[int](np.round((dx - np.floor(dx))*2)) % 2
    yq = np.cast[int](np.round((dy - np.floor(dy))*2)) % 2
    
    ### Test
    if False:
        xf = ((dx - np.floor(dx)))
        yf = ((dy - np.floor(dy)))

        colors = np.array([['r','g'],['b','k']])
        plt.scatter(xf, yf, c=colors[xq, yq])
    
    index = np.arange(len(dx))
    out = {}
    for i in range(4):
        match = xq+2*yq == i
        if match.sum() > 0:
            out[i] = index[match]
    
    return out

def combine_figs():
    """
    Combine FIGS exposures split by offset pixel quadrant
    """
    from stsci.tools import asnutil
    
    #all_asn = glob.glob('figs-g*-g1*asn.fits')
    all_asn = []
    all_asn.extend(glob.glob('g[ns][0-9]*g102*asn.fits'))
    all_asn.extend(glob.glob('gdn*g102*asn.fits'))
    grism = 'g102'
    
    #all_asn = glob.glob('gn-z10*-g1*asn.fits')
    #all_asn.extend(glob.glob('colfax-*g14*asn.fits'))
    #all_asn = glob.glob('goodsn-*g14*asn.fits')
    #grism = 'g141'
    
    roots = np.unique(['-'.join(asn.split('-')[:2]) for asn in all_asn])
    for root in roots:
        all_asn = glob.glob('%s*%s*asn.fits' %(root, grism))
        angles = np.unique([asn.split('-')[-2] for asn in all_asn])
        for angle in angles:
            asn_files = glob.glob('%s*-%s-%s*asn.fits' %(root, angle, grism))
            
            grism_files = [] 
            for file in asn_files:
                asn = asnutil.readASNTable(file)
                grism_files.extend(['%s_flt.fits' %(flt) for flt in asn['order']])
            
            print '%s-%s %d' %(root, angle, len(grism_files))
            combine_quadrants(files=grism_files, output='%s-%s-%s_cmb.fits' %(root, angle, grism))
            
def combine_quadrants(files=[], output='images_cmb.fits', pixfrac=0.5, 
                 kernel='point'):
    """TBD
    """
    h, dx, dy = get_shifts(files, ref_pixel=[507, 507])
    out = split_pixel_quadrant(dx, dy)
    for q in out:
        print 'Quadrant %d, %d files' %(q, len(out[q]))
        combine_flt(files=np.array(files)[out[q]],
                    output=output.replace('_cmb.fits', '_q%d_cmb.fits' %(q)), 
                    grow=1, pixfrac=pixfrac, kernel=kernel)
                    
def combine_flt(files=[], output='combined_flt.fits', grow=2,
                add_padding=True, ds9=None, split_quadrants=False,
                verbose=True, clobber=True, pixfrac=0.5, kernel='point'):
    """Drizzle distorted frames to an "interlaced" image
    TBD
    """
    import numpy.linalg
    from stsci.tools import asnutil
    
    ###  `files` is an ASN filename, not  a list of exposures
    if '_asn.fits' in files:
        asn = asnutil.readASNTable(files)
        files = ['%s_flt.fits' %(flt) for flt in asn['order']]
        if output == 'combined_flt.fits':
            output = '%s_cmb.fits' %(asn['output'])
            
    if False:
        files=glob.glob('ibhj3*flt.fits')
        files.sort()
        grism_files = files[1::2]

        ### FIGS
        info = catIO.Table('info')
        pas = np.cast[int](info['PA_V3']*10)/10.
        pa_list = np.unique(pas)
        grism_files = info['FILE'][(info['FILTER'] == 'G102') & 
                                   (pas == pa_list[0])]
        
        files = grism_files
        #utils = grizlidev.utils
        
    f0 = pyfits.open(files[0])
    h0 = f0[0].header.copy()
    h0['EXPTIME'] = 0.
    h0['NFILES'] = (len(files), 'Number of combined files')
    
    out_wcs = pywcs.WCS(f0[1].header, relax=True)
    out_wcs.pscale = utils.get_wcs_pscale(out_wcs)
    # out_wcs.pscale = np.sqrt(out_wcs.wcs.cd[0,0]**2 +
    #                          out_wcs.wcs.cd[1,0]**2)*3600.
    
    ### Compute maximum offset needed for padding
    if add_padding:
        ra0, de0 = out_wcs.all_pix2world([0],[0],0)
    
        x0 = np.zeros(len(files))
        y0 = np.zeros(len(files))
    
        for i, file in enumerate(files):
            hx = pyfits.getheader(file, 0)
            h0['EXPTIME'] += hx['EXPTIME']
            h0['FILE%04d' %(i)] = file, 'Included file #%d' %(i)
        
            h = pyfits.getheader(file, 1)
            flt_wcs = pywcs.WCS(h, relax=True)
            x0[i], y0[i] = flt_wcs.all_world2pix(ra0, de0, 0)
    
        xmax = np.abs(x0).max()
        ymax = np.abs(y0).max()
        padx = 50*int(np.ceil(xmax/50.))
        pady = 50*int(np.ceil(ymax/50.))
        pad = np.maximum(padx, pady)*grow

        if verbose:
            print 'Maximum shift (x, y) = (%6.1f, %6.1f), pad=%d' %(xmax,
                                                                    ymax,
                                                                    pad)
    else:
        pad = 0
        
    inter_wcs = out_wcs.deepcopy()
    if grow > 1:
        inter_wcs.wcs.cd /= grow
        for i in range(inter_wcs.sip.a_order+1):
            for j in range(inter_wcs.sip.a_order+1):
                inter_wcs.sip.a[i,j] /= grow**(i+j-1)

        for i in range(inter_wcs.sip.b_order+1):
            for j in range(inter_wcs.sip.b_order+1):
                inter_wcs.sip.b[i,j] /= grow**(i+j-1)

        inter_wcs._naxis1 *= grow
        inter_wcs._naxis2 *= grow
        inter_wcs.wcs.crpix *= grow
        inter_wcs.sip.crpix[0] *= grow
        inter_wcs.sip.crpix[1] *= grow

        if grow > 1:
            inter_wcs.wcs.crpix += grow/2.
            inter_wcs.sip.crpix[0] += grow/2.
            inter_wcs.sip.crpix[1] += grow/2.
    
    inter_wcs._naxis1 += pad
    inter_wcs._naxis2 += pad
    inter_wcs.wcs.crpix += pad
    inter_wcs.sip.crpix[0] += pad
    inter_wcs.sip.crpix[1] += pad

    outh = inter_wcs.to_header(relax=True)
    for key in outh:
        if key.startswith('PC'):
            outh.rename_keyword(key, key.replace('PC','CD'))
    
    outh['GROW'] = grow, 'Grow factor'
    outh['PAD'] = pad, 'Image padding'
    
    sh = (1014*grow + 2*pad, 1014*grow + 2*pad)
    outsci = np.zeros(sh, dtype=np.float32)
    outwht = np.zeros(sh, dtype=np.float32)
    outctx = np.zeros(sh, dtype=np.int32)

    ## Pixel area map
    # PAM_im = pyfits.open(os.path.join(os.getenv('iref'), 'ir_wfc3_map.fits'))
    # PAM = PAM_im[1].data
    
    for i, file in enumerate(files):
        im = pyfits.open(file)
        
        if verbose:
            print '%3d %s %6.1f %6.1f %10.2f' %(i+1, file, x0[i], y0[i],
                                               im[0].header['EXPTIME'])

        dq = utils.unset_dq_bits(im['DQ'].data, okbits=608,
                                           verbose=False)
        wht = 1./im['ERR'].data**2
        wht[(im['ERR'].data == 0) | (dq > 0) | (~np.isfinite(wht))] = 0
        wht[im['SCI'].data < -3*im['ERR'].data] = 0

        wht = np.cast[np.float32](wht)

        exp_wcs = pywcs.WCS(im[1].header, relax=True)
        exp_wcs.pscale = utils.get_wcs_pscale(exp_wcs)
                                 
        #pf = 0.5
        # import drizzlepac.wcs_functions as dwcs
        # xx = out_wcs.deepcopy()
        # #xx.all_pix2world = xx.wcs_world2pix
        # map = dwcs.WCSMap(exp_wcs, xx)

        astrodrizzle.adrizzle.do_driz(im['SCI'].data, exp_wcs, wht,
                                      inter_wcs, outsci, outwht, outctx,
                                      1., 'cps', 1, 
                                      wcslin_pscale=exp_wcs.pscale,
                                      uniqid=1,
                                      pixfrac=pixfrac, kernel=kernel, 
                                      fillval=0, stepsize=10,
                                      wcsmap=SIP_WCSMap)   

        if ds9 is not None:
            ds9.view(outsci, header=outh)

    #outsci /= out_wcs.pscale**2
    rms = 1/np.sqrt(outwht)
    mask = (outwht == 0) | (rms > 100)
    rms[mask] = 0
    outsci[mask] = 0.
    
    hdu = [pyfits.PrimaryHDU(header=h0)]
    hdu.append(pyfits.ImageHDU(data=outsci/grow**2, header=outh, name='SCI'))
    hdu.append(pyfits.ImageHDU(data=rms/grow**2, header=outh, name='ERR'))
    hdu.append(pyfits.ImageHDU(data=mask*1024, header=outh, name='DQ'))
    
    pyfits.HDUList(hdu).writeto(output, clobber=clobber, output_verify='fix')
    
#
# Default mapping function based on PyWCS
class SIP_WCSMap:
    def __init__(self,input,output,origin=1):
        """Sample class to demonstrate how to define a coordinate transformation

        Modified from `drizzlepac.wcs_functions.WCSMap` to use full SIP header
        in the `forward` and `backward` methods. Use this class to drizzle to
        an output distorted WCS, e.g., 
            
            >>> drizzlepac.astrodrizzle.do_driz(..., wcsmap=SIP_WCSMap)
        """

        # Verify that we have valid WCS input objects
        self.checkWCS(input,'Input')
        self.checkWCS(output,'Output')

        self.input = input
        self.output = copy.deepcopy(output)
        #self.output = output

        self.origin = origin
        self.shift = None
        self.rot = None
        self.scale = None

    def checkWCS(self,obj,name):
        try:
            assert isinstance(obj, pywcs.WCS)
        except AssertionError:
            print(name +' object needs to be an instance or subclass of a PyWCS object.')
            raise

    def forward(self,pixx,pixy):
        """ Transform the input pixx,pixy positions in the input frame
            to pixel positions in the output frame.

            This method gets passed to the drizzle algorithm.
        """
        # This matches WTRAXY results to better than 1e-4 pixels.
        skyx,skyy = self.input.all_pix2world(pixx,pixy,self.origin)
        #result= self.output.wcs_world2pix(skyx,skyy,self.origin)
        result= self.output.all_world2pix(skyx,skyy,self.origin)
        return result

    def backward(self,pixx,pixy):
        """ Transform pixx,pixy positions from the output frame back onto their
            original positions in the input frame.
        """
        #skyx,skyy = self.output.wcs_pix2world(pixx,pixy,self.origin)
        skyx,skyy = self.output.all_pix2world(pixx,pixy,self.origin)
        result = self.input.all_world2pix(skyx,skyy,self.origin)
        return result

    def get_pix_ratio(self):
        """ Return the ratio of plate scales between the input and output WCS.
            This is used to properly distribute the flux in each pixel in 'tdriz'.
        """
        return self.output.pscale / self.input.pscale

    def xy2rd(self,wcs,pixx,pixy):
        """ Transform input pixel positions into sky positions in the WCS provided.
        """
        return wcs.all_pix2world(pixx,pixy,1)
    def rd2xy(self,wcs,ra,dec):
        """ Transform input sky positions into pixel positions in the WCS provided.
        """
        return wcs.wcs_world2pix(ra,dec,1)
