import os, sys
import numpy as np

def mkdir(fn, opt=''):
    if opt == 'parent':  # until the last path separator
        fn = fn[:fn.rfind(os.path.sep)]
    
    if not os.path.exists(fn):
        if 'all' in opt:
            os.makedirs(fn)
        else:
            os.mkdir(fn)


def readVol(filename, z=None, kk=None, image_type='im'):
    from imageio import imread
    filename = str(filename)
    # image_type='seg': 1-channel
    if filename[-2:] == 'h5':
        import h5py
        tmp = h5py.File(filename, 'r')
        if kk is None:
            kk = list(tmp)[0]
        if z is not None:
            out = np.array(tmp[kk][z])
        else:
            out = np.array(tmp[kk])
    elif filename[-3:] == 'zip':
        import zarr
        tmp = zarr.open_group(filename)
        if kk is None:
            kk = tmp.info_items()[-1][1]
            if ',' in kk:
                kk = kk[:kk.find(',')]
        out = np.array(tmp[kk][z])
    elif filename[-3:] in ['jpg', 'png', 'tif', 'iff']:
        import imageio
        if z is None:  # image
            out = imageio.imread(filename)
        else:  # volume data (tif)
            out = imageio.volread(filename)
    elif filename[-3:] == 'txt':
        out = np.loadtxt(filename)
    elif filename[-3:] == 'npy':
        out = np.load(filename)
    else:
        raise "Can't read the file %s" % filename
    return out


def readImage(filename):
    import imageio
    image = imageio.imread(filename)
    return image


# h5 files
def readH5(filename, datasetname=None):
    import h5py
    fid = h5py.File(filename, 'r')
    if datasetname is None:
        if sys.version[0] == '2':  # py2
            datasetname = fid.keys()
        else:  # py3
            datasetname = list(fid)
    if len(datasetname) == 1:
        datasetname = datasetname[0]
    if isinstance(datasetname, (list,)):
        out = [None] * len(datasetname)
        for di, d in enumerate(datasetname):
            out[di] = np.array(fid[d])
        return out
    else:
        return np.array(fid[datasetname])


def writeH5(filename, dtarray, datasetname='main'):
    import h5py
    fid = h5py.File(filename, 'w')
    if isinstance(datasetname, (list,)):
        for i, dd in enumerate(datasetname):
            ds = fid.create_dataset(dd, dtarray[i].shape, compression="gzip", dtype=dtarray[i].dtype)
            ds[:] = dtarray[i]
    else:
        ds = fid.create_dataset(datasetname, dtarray.shape, compression="gzip", dtype=dtarray.dtype)
        ds[:] = dtarray
    fid.close()


def readTxt(filename):
    a = open(filename)
    content = a.readlines()
    a.close()
    return content


def writeTxt(filename, content):
    a = open(filename, 'w')
    if isinstance(content, (list,)):
        for ll in content:
            a.write(ll)
            if '\n' not in ll:
                a.write('\n')
    else:
        a.write(content)
    a.close()


def writeGif(outname, filenames, ratio=1, duration=0.5):
    import imageio
    from scipy.ndimage import zoom
    out = [None] * len(filenames)
    for fid, filename in enumerate(filenames):
        image = imageio.imread(filename)
        if ratio != 1:
            if image.ndim == 2:
                image = zoom(image, ratio, order=1)
            else:
                image = np.stack([zoom(image[:, :, d], ratio, order=1) for d in range(3)], axis=2)
        out[fid] = image
    imageio.mimsave(outname, out, 'GIF', duration=duration)