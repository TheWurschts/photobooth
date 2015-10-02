import gphoto2 as gp
error, camera = gp.gp_camera_new()
print('Please connect and switch on your camera')
while True:
    try:
        camera.init(context)
    except gp.GPhoto2Error as ex:
        if ex.code == gp.GP_ERROR_MODEL_NOT_FOUND:
            # no camera, try again in 2 seconds
            time.sleep(2)
            continue
        # some other error we can't handle here
        raise
    # operation completed successfully so exit loop
    break