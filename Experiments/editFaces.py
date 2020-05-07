"""
Script for performing the qualitative analysis.
"""
from PIL import Image
import os
import numpy as np
import tensorflow as tf

#--------------------------------------------------------------------
#-HELPERS------------------------------------------------------------
#--------------------------------------------------------------------
def normalize_image(img, maximum):
    """
    Normalizes all pixels to values between 0 and maximum.
    
    @param img: numpy array 
    @param maximum: scalar value
    
    @return numpy array of same size as img
    """
    img /= img.max()/maximum
    return img

def save_image_black_and_white(img_array, path):
    """
    Saves a black and white image from a two-dimensional numpy array under path.
    
    @param img_array: two-dimensional numpy array 
    @param path: string
    """
    img = Image.fromarray(img_array)
    img = img.convert('L')
    img.save(path)
    
def save_image(img_array, path):
    """
    Saves an image from a three-dimensional numpy array under path.
    
    @param img_array: two-dimensional numpy array 
    @param path: string
    """
    img = Image.fromarray(img_array.astype('uint8'))
    img = img.convert('RGB')
    img.save(path)

def get_image_array(path, image_size=None):
    """
    Reads image from file and transforms it to numpy array.
    
    @param path: string
    @param image_size: (optional) size of the image
    
    @param img_array: numpy array 
    """
    if image_size == None:
        return np.asarray(Image.open(path)).astype(np.float32)
    return np.asarray(Image.open(path).resize(image_size)).astype(np.float32)

def get_max_difference(img1, img2):
    """
    Computes maximum channel-difference of two images per pixel.
    
    @param img1: numpy array [size x]x[size y]x3
    @param img2: numpy array [size x]x[size y]x3
    
    @return: numpy array [size x]x[size y]
    """
    # Calculate the absolute difference on each channel separately
    red_error = np.fabs(np.subtract(img2[:,:,0], img1[:,:,0]))
    green_error = np.fabs(np.subtract(img2[:,:,1], img1[:,:,1]))
    blue_error = np.fabs(np.subtract(img2[:,:,2], img1[:,:,2]))
    
    # Calculate the maximum error for each pixel
    return np.maximum(np.maximum(red_error, green_error), blue_error)

def get_generated_images(path, p=96):
    """
    Cuts generated images from image saved in network output format.
    
    @param path: path to image to cut generated images from.
    
    @return: numpy array of shape 49x96x96x3
    """
    img = get_image_array(path)
    res = []
    for r in range(7):
        for c in range(7):
            single_image =  img[r*p:(r+1)*p, p*(c+3):p*(c+4)]
            res.append(single_image)          
    return np.asarray(res)
    
def tile_to_square(images):
    """
    Transforms numpy array of 49x96x96 to numpy array of 672x672 by tiling.
    
    @param images: numpy array of shape 49x96x96
    
    @return: numpy array of shape 672x672
    """
    # Build final image from components
    frame = np.zeros([96*7, 96*7])
    for index, image in enumerate(images):
        index_column = index % 7
        index_row    = index // 7
        frame[(index_row*96):((index_row+1)*96),(index_column*96):((index_column+1)*96)] = image
    return frame

def save_generated_output(inp, generated_outp, path):
    """
    Save the output generated by the network.
    """
    # Tile black background
    black_image = np.zeros((1, 96, 96, 3))
    black_image3 = np.tile(black_image, (3, 1, 1, 1))
    
    # Build final image from components
    final_image_list = np.concatenate([black_image3,generated_outp[:7],
                                       black_image3,generated_outp[7:14],
                                       black_image3,generated_outp[14:21],
                                       black_image,inp,black_image,generated_outp[21:28],
                                       black_image3,generated_outp[28:35],
                                       black_image3,generated_outp[35:42],
                                       black_image3,generated_outp[42:]])
    
    # Transform into savable format
    final_image = np.zeros((96*7, 96*10, 3))    
    for index, image in enumerate(final_image_list):
        index_column = index % 10
        index_row    = index // 10
        final_image[(index_row*96):((index_row+1)*96),(index_column*96):((index_column+1)*96)] = image
    
    # Normalize + save image
    save_image((final_image+1)*255/2, path)
    
def load_image_as_network_input(image_path):
    """
    Load image and normalize it to pixel values in [-1,1].
    
    @param image_path: path to image (string)
    
    @return: numpy array of size 96x96x3
    """
    image = get_image_array(image_path, image_size=(96,96))
    image = normalize_image(image, 2)
    return image-1

#--------------------------------------------------------------------
#-MAIN METHODS-------------------------------------------------------
#--------------------------------------------------------------------
def compute_overall_difference(path, save_name):
    """
    Computes the overall differences between the neutral expression image and emotional
    images of all images found in paths. 
    
    @paths: path to existing directory (string)
    
    @return: numpy array of size 672x672 
    """
    img_paths = [path+x for x in os.listdir(path)]
    
    res = np.zeros((672,672))
    allover_max = 0

    for img_path in img_paths:
        # read generated images from file
        gen_images = get_generated_images(img_path)
        neutral_generated_image = gen_images[24]

        # compute differences between every image and the image of the neutral face
        differences = np.asarray([get_max_difference(im,neutral_generated_image) for im in gen_images])

        # Tile "difference"-images to a 7x7 square
        differences_square = tile_to_square(differences)

        m = differences_square.max()
        if m > allover_max: allover_max = m

        res = res + differences_square
    
    differences = normalize_image(res, allover_max)
    save_image_black_and_white(differences, save_name)


def apply_network_to_images_of_dir(path_to_dir, path_to_out_dir):
    """
    Applies the trained network to all images found in path_to_dir for 49 emotions respectively.
    Saves the output in path_to_out_dir.
    
    @param path_to_dir: path to existing directory (string)
    @param path_to_out_dir: path to existing directory (string)
    """
    # valence
    valence = np.arange(0.75, -0.751, -0.25)
    valence = np.repeat(valence, 7).reshape((49, 1))

    # arousal
    arousal = [np.arange(0.75, -0.751, -0.25)]
    arousal = np.repeat(arousal, 7, axis=0)
    arousal = np.asarray([item for sublist in arousal for item in sublist]).reshape((49, 1))

    config = tf.compat.v1.ConfigProto()
    config.gpu_options.allow_growth = True

    with tf.Session(config=config) as sess:
        with tf.device('/device:CPU:0'):
            # restore graph
            new_saver = tf.train.import_meta_graph('checkpoint/01_model.meta')
            new_saver.restore(sess, tf.train.latest_checkpoint('./checkpoint'))
            graph = tf.get_default_graph()

            # create feed dict
            arousal_tensor = graph.get_tensor_by_name("arousal_labels:0")
            valence_tensor = graph.get_tensor_by_name("valence_labels:0")
            images_tensor = graph.get_tensor_by_name("input_images:0")

            # load input
            files_already = os.listdir(path_to_out_dir)

            files = [f for f in os.listdir(path_to_dir) if not f in files_already]

            for file in files:
                i = load_image_as_network_input(path_to_dir+file).reshape((1,96,96,3))
                query_images = np.tile(i, (49, 1, 1, 1))

                # create input for net
                feed_dict ={arousal_tensor:arousal,valence_tensor:valence, images_tensor:query_images}
                op_to_restore = sess.graph.get_tensor_by_name("generator/Tanh:0")

                # run
                x = sess.run(op_to_restore,feed_dict)

                # save
                save_generated_output(i, x, path_to_out_dir+file)

#--------------------------------------------------------------------
#--------------------------------------------------------------------
#--------------------------------------------------------------------      


if __name__ == "__main__":
    # Uncomment for feeding images from './celebs/' to the trained model (may take a few minutes)
    apply_network_to_images_of_dir('./celebs/', './celebs_edited/')

















      
            
