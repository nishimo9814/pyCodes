import cv2
import numpy as np
from matplotlib import pyplot as plt
from pylab import *
# from sfm import triangulate
# from sfm import compute_P_from_essential
# from homography import make_homog
import sfm
import homography
from mpl_toolkits.mplot3d import Axes3D
import tkinter as Tk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# 3次元再構成
# １、2つの２次元画像から特徴点を対応付ける行列Fを求める（エピポーラ拘束）
#     x2 * F * x1 =0
# 　２、Fをカメラの内部行列で正規化したものをEとする
# 　３、Eから外部行列Pを推定する
# 　４、x1, x2, PからXを求める（三角測量）

def calcRmat(agl_deg, nVec):
    agl = np.deg2rad(agl_deg)
    Rmat = np.array([
        [np.cos(agl) + nVec[0] * nVec[0] * (1 - np.cos(agl)), nVec[0] * nVec[1] * (1 - np.cos(agl)) - nVec[2] * np.sin(agl),
         nVec[0] * nVec[2] * (1 - np.cos(agl)) + nVec[1] * np.sin(agl)],
        [nVec[0] * nVec[1] * (1 - np.cos(agl)) + nVec[2] * np.sin(agl), np.cos(agl) + nVec[1] * nVec[1] * (1 - np.cos(agl)),
         nVec[1] * nVec[2] * (1 - np.cos(agl)) - nVec[0] * np.sin(agl)],
        [nVec[0] * nVec[2] * (1 - np.cos(agl)) - nVec[1] * np.sin(agl),
         nVec[1] * nVec[2] * (1 - np.cos(agl)) + nVec[0] * np.sin(agl), np.cos(agl) + nVec[2] * nVec[2] * (1 - np.cos(agl))]
    ])
    return Rmat

def calcRmatDeg(Rmat):
    theta = ( Rmat[0][0] + Rmat[1][1] + Rmat[2][2] - 1.0 ) * 0.5
    delta = 1.0e-6
    if (abs(theta) - 1 ) > delta: return -1, -200, -200
    val_rad = np.arccos(theta)
    val_deg = np.rad2deg(val_rad)

    ny = (Rmat[0][2] - Rmat[2][0]) * 0.5 * ( 1.0 / np.sin(theta))
    nx = (Rmat[2][1] - Rmat[1][2]) * 0.5 * ( 1.0 / np.sin(theta))
    nz = (Rmat[1][0] - Rmat[0][1]) * 0.5 * ( 1.0 / np.sin(theta))
    nvec = np.array([nx, ny, nz])

    Rmat2 = calcRmat(val_deg, nvec)
    RmatDef = Rmat - Rmat2

    DefNrm = np.linalg.norm(RmatDef, "fro")
    if DefNrm > delta: return -1, val_deg, DefNrm

    return 1, val_deg, DefNrm

class TKExample():

    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        # 設定
        self.Focal = 200
        self.Imgwidth, self.Imgheight = 640, 480
        self.Ang_cam2 = 0
        self.Trans_x_cam2 = 0
        self.Trans_y_cam2 = 0
        self.Trans_z_cam2 = 4
        #カメラ内部パラメータ
        self.K = np.array([[self.Focal, 0, self.Imgwidth / 2],
                           [0, self.Focal, self.Imgheight / 2],
                           [0, 0, 1]], float)
        #カメラ外部パラメータ
        self.P1 = np.array([[1, 0, 0, 0],
                            [0, 1, 0, 0],
                            [0, 0, 1, 0]])

        nVec = np.array([1,0,0])
        Rmat = calcRmat(self.Ang_cam2, nVec)
        # Rmat, jac = cv2.Rodrigues(np.array([[aglRadx, aglRady, aglRadz]], float))
        self.P2 = np.array([[Rmat[0][0], Rmat[0][1], Rmat[0][2], self.Trans_x_cam2],
                              [Rmat[1][0], Rmat[1][1], Rmat[1][2], self.Trans_y_cam2],
                              [Rmat[2][0], Rmat[2][1], Rmat[2][2], self.Trans_z_cam2]])

        # 3dオブジェクト
        self.ll = [[0, 1], [0, 2], [0, 3], [1, 4], [1, 5], [2, 4],
              [2, 6], [3, 5], [3, 6], [4, 7], [5, 7], [6, 7]]

        self.Xpt = [[2, 0, 2, 3, 0.6, 3, 3, 3],
                    [2, 2, 3, 2, 4, 2, 3, 3],
                    [4, 1, 4, 4, 1, 1, 4, 1],
                    [1, 1, 1, 1, 1, 1, 1, 1]]

        # Xp_add = [[1, 1, 2.5, 1.8, 1.8, 3, 3],
        #           [2, 2.5, 2.5, 3, 3, 3, 2.5],
        #           [2.5, 2.5, 4, 2.5, 1, 2.5, 2.5],
        #           [1, 1, 1, 1, 1, 1, 1]]
        # self.Xpt[0].extend(Xp_add[0])
        # self.Xpt[1].extend(Xp_add[1])
        # self.Xpt[2].extend(Xp_add[2])
        # self.Xpt[3].extend(Xp_add[3])

        # self.llcolor = ["g","c","c","m","m","g","c","g","c","m","m","g"]
        self.llcolor = ["m", "m", "m", "m", "m", "m", "m", "m", "m", "m", "m", "m"]

        # 3dから2d画像を作成
        fig2d = plt.figure(figsize=(10, 6))
        self.ax1 = fig2d.add_subplot(325)
        self.ax2 = fig2d.add_subplot(326)
        self.draw2d()

        self.ax_wld = fig2d.add_subplot(321, projection='3d')
        self.draw3d_obj_wld()

        self.ax_rcn = fig2d.add_subplot(322, projection='3d')
        self.draw3d_reconstracted()

        self.ax_rcn_est = fig2d.add_subplot(323, projection='3d')
        self.draw3d_reconstracted_estP()

        # self.ax_cam1 = fig2d.add_subplot(334, projection='3d')
        # self.ax_cam2 = fig2d.add_subplot(335, projection='3d')
        # self.draw3d_obj_cam()

        root = Tk.Tk()

        # Canvasを生成
        self.canvas = FigureCanvasTkAgg(fig2d, master=root)
        # canvas.get_tk_widget().pack(side=Tk.BOTTOM, expand=0)
        # canvas._tkcanvas.pack(side=Tk.BOTTOM, expand=0)
        self.canvas.get_tk_widget().grid(row=1, column=0, columnspan=6, pady=(15, 15), padx=(25, 25),
                                    sticky=Tk.N + Tk.S + Tk.E + Tk.W)

        self.bt = Tk.Button(root, text='UPDATE', command=self.updatePrm)
        self.bt.grid(row=2, column=0, columnspan=6)
        self.lb00 = Tk.Label(root, text='focal')
        self.lb00.grid(row=3, column=0, sticky=Tk.W)
        self.et00 = Tk.Entry(root)
        self.et00.insert(Tk.END, "200")
        self.et00.grid(row=3, column=1, sticky=Tk.W)

        self.lb01 = Tk.Label(root, text='img width')
        self.lb01.grid(row=4, column=0, sticky=Tk.W)
        self.et01 = Tk.Entry(root)
        self.et01.insert(Tk.END, "640")
        self.et01.grid(row=4, column=1, sticky=Tk.W)

        self.lb02 = Tk.Label(root, text='img height')
        self.lb02.grid(row=4, column=2, sticky=Tk.W)
        self.et02 = Tk.Entry(root)
        self.et02.insert(Tk.END, "480")
        self.et02.grid(row=4, column=3, sticky=Tk.W)

        self.lb10 = Tk.Label(root, text='Cam2 external Param')
        self.lb10.grid(row=8, column=0, sticky=Tk.W)

        self.lb11 = Tk.Label(root, text='ang')
        self.lb11.grid(row=9, column=0, sticky=Tk.W)
        self.et11 = Tk.Entry(root)
        self.et11.insert(Tk.END, "0")
        self.et11.grid(row=9, column=1, sticky=Tk.W)

        self.lb14 = Tk.Label(root, text='trans x')
        self.lb14.grid(row=10, column=0, sticky=Tk.W)
        self.et14 = Tk.Entry(root)
        self.et14.insert(Tk.END, "0")
        self.et14.grid(row=10, column=1, sticky=Tk.W)

        self.lb15 = Tk.Label(root, text='trans y')
        self.lb15.grid(row=10, column=2, sticky=Tk.W)
        self.et15 = Tk.Entry(root)
        self.et15.insert(Tk.END, "0")
        self.et15.grid(row=10, column=3, sticky=Tk.W)

        self.lb16 = Tk.Label(root, text='trans z')
        self.lb16.grid(row=10, column=4, sticky=Tk.W)
        self.et16 = Tk.Entry(root)
        self.et16.insert(Tk.END, "4")
        self.et16.grid(row=10, column=5, sticky=Tk.W)

        root.mainloop()

    def updatePrm(self):
        focal = float(self.et00.get())
        imgwidth, imgheight = float(self.et01.get()), float(self.et02.get())
        ang_cam2 = float(self.et11.get())
        trans_x_cam2 = float(self.et14.get())
        trans_y_cam2 = float(self.et15.get())
        trans_z_cam2 = float(self.et16.get())
        self.setCamprm(focal, imgwidth, imgheight,
                  ang_cam2,  trans_x_cam2, trans_y_cam2, trans_z_cam2)
        self.draw2d()
        # self.draw3d_obj_wld()
        # self.draw3d_obj_cam()
        self.draw3d_reconstracted()
        self.draw3d_reconstracted_estP()
        self.canvas.draw()

    def setCamprm(self, focal, imgwidth, imgheight,
                  ang_cam2, trans_x_cam2, trans_y_cam2, trans_z_cam2):
        self.Focal = focal
        self.Imgwidth, self.Imgheight = imgwidth, imgheight
        self.Ang_cam2 = ang_cam2
        self.Trans_x_cam2 = trans_x_cam2
        self.Trans_y_cam2 = trans_y_cam2
        self.Trans_z_cam2 = trans_z_cam2
        self.K = np.array([[self.Focal, 0, self.Imgwidth / 2], [0, self.Focal, self.Imgheight / 2], [0, 0, 1]], float)

        nVec = np.array([1,0,0])
        Rmat = calcRmat(self.Ang_cam2, nVec)
        # Rmat, jac = cv2.Rodrigues(np.array([[aglRadx, aglRady, aglRadz]], float))
        self.P2 = np.array([[Rmat[0][0], Rmat[0][1], Rmat[0][2], self.Trans_x_cam2],
                              [Rmat[1][0], Rmat[1][1], Rmat[1][2], self.Trans_y_cam2],
                              [Rmat[2][0], Rmat[2][1], Rmat[2][2], self.Trans_z_cam2]])

    def draw3d_obj_cam(self):
        self.ax_cam1.cla()
        self.ax_cam2.cla()

        # 　カメラ座標 ( X', Y', Z', 1 )
        x1p = self.P1.dot(self.Xpt)
        x2p = self.P2.dot(self.Xpt)

        self.ax_cam1.set_title("obj cam1 cam")
        self.ax_cam1.set_xlim([-5, 5])
        self.ax_cam1.set_ylim([-5, 5])
        self.ax_cam1.set_zlim([-5, 5])
        self.ax_cam1.set_xlabel("x")
        self.ax_cam1.set_ylabel("y")
        self.ax_cam1.set_zlabel("z")
        self.ax_cam1.grid(which = "major", axis = "x")
        self.ax_cam1.grid(which="major", axis="y")
        org = np.array([0, 0, 0])
        xv = np.array([1, 0, 0])
        yv = np.array([0, 1, 0])
        zv = np.array([0, 0, 1])
        self.ax_cam1.quiver(org[0], org[1], org[2], xv[0], xv[1], xv[2], length=1, color='orange')
        self.ax_cam1.quiver(org[0], org[1], org[2], yv[0], yv[1], yv[2], length=1, color='orange')
        self.ax_cam1.quiver(org[0], org[1], org[2], zv[0], zv[1], zv[2], length=1, color='orange')

        self.ax_cam2.set_title("obj cam2 cam")
        self.ax_cam2.set_xlim([-5, 5])
        self.ax_cam2.set_ylim([-5, 5])
        self.ax_cam2.set_zlim([-5, 5])
        self.ax_cam2.set_xlabel("x")
        self.ax_cam2.set_ylabel("y")
        self.ax_cam2.set_zlabel("z")
        self.ax_cam2.grid(which = "major", axis = "x")
        self.ax_cam2.grid(which="major", axis="y")
        org = np.array([0, 0, 0])
        xv = np.array([1, 0, 0])
        yv = np.array([0, 1, 0])
        zv = np.array([0, 0, 1])
        self.ax_cam2.quiver(org[0], org[1], org[2], xv[0], xv[1], xv[2], length=1, color='orange')
        self.ax_cam2.quiver(org[0], org[1], org[2], yv[0], yv[1], yv[2], length=1, color='orange')
        self.ax_cam2.quiver(org[0], org[1], org[2], zv[0], zv[1], zv[2], length=1, color='orange')

        for i,l in enumerate(self.ll):
            x = np.array([x1p[0][l[0]], x1p[0][l[1]]])
            y = np.array([x1p[1][l[0]], x1p[1][l[1]]])
            z = np.array([x1p[2][l[0]], x1p[2][l[1]]])
            self.ax_cam1.plot(x, y, z, marker='.', markersize=5, color=self.llcolor[i])
            x = np.array([x2p[0][l[0]], x2p[0][l[1]]])
            y = np.array([x2p[1][l[0]], x2p[1][l[1]]])
            z = np.array([x2p[2][l[0]], x2p[2][l[1]]])
            self.ax_cam2.plot(x, y, z, marker='.', markersize=5, color=self.llcolor[i])

    def draw2d(self):
        self.ax1.cla()
        self.ax2.cla()

        # カメラ行列
        A1 = self.K.dot(self.P1)
        A2 = self.K.dot(self.P2)

        # 　画像座標 ( sx, sy, s )
        x1p = A1.dot(self.Xpt)
        x2p = A2.dot(self.Xpt)

        # sで正規化 (x, y, 1)
        for i in range(3):
            x1p[i] /= x1p[2]
            x2p[i] /= x2p[2]

        self.ax1.set_xlim([0, self.Imgwidth])
        self.ax1.set_ylim([0, self.Imgheight])
        self.ax1.set_xlabel("x_img")
        self.ax1.set_ylabel("y_img")
        self.ax1.set_title("obj cam1 img")
        self.ax1.grid(which = "major", axis = "x")
        self.ax1.grid(which="major", axis="y")

        self.ax2.set_xlim([0, self.Imgwidth])
        self.ax2.set_ylim([0, self.Imgheight])
        self.ax2.set_xlabel("x_img")
        self.ax2.set_ylabel("y_img")
        self.ax2.set_title("obj cam2 img")
        self.ax2.grid(which="major", axis="x")
        self.ax2.grid(which="major", axis="y")
        #self.ax1.axis('scaled')
        for i,l in enumerate(self.ll):
            x = np.array([x1p[0][l[0]], x1p[0][l[1]]])
            y = np.array([x1p[1][l[0]], x1p[1][l[1]]])
            # self.ax1.plot(x, y, marker='.', markersize=5, color='red')
            self.ax1.plot(x, y, marker='.', markersize=5, color=self.llcolor[i])
            x = np.array([x2p[0][l[0]], x2p[0][l[1]]])
            y = np.array([x2p[1][l[0]], x2p[1][l[1]]])
            #self.ax2.plot(x, y, marker='.', markersize=5, color='blue')
            self.ax2.plot(x, y, marker='.', markersize=5, color=self.llcolor[i])

        # draw epipolar line
        ## calcurate F: x1 * F * x2
        F = sfm.compute_fundamental(x1p, x2p)
        ## calc epi poler
        e1 = sfm.compute_epipole(F)
        e2 = sfm.compute_epipole(F.T)

        print("F:", F)

        numLine = len(x1p[0,:])
        for i in range(numLine):
            # epiline on img1
            line = dot(F, x2p[:,i])
            t = linspace(0, self.Imgwidth, 100)
            lt = array([(line[2] + line[0] * tt) / (-line[1]) for tt in t])
            # ndx = (lt >= 0) & (lt < self.Imgheight)
            # self.ax1.plot(t[ndx], lt[ndx], linewidth=1)
            self.ax1.plot(t, lt, linewidth=1)
            self.ax1.plot(e1[0]/e1[2], e1[1]/e1[2],'r*')

            # epiline on img1
            line = dot(F.T, x1p[:,i])
            t = linspace(0, self.Imgwidth, 100)
            lt = array([(line[2] + line[0] * tt) / (-line[1]) for tt in t])
            self.ax2.plot(t, lt, linewidth=1)
            self.ax2.plot(e2[0]/e2[2], e2[1]/e2[2],'r*')

    def draw3d_obj_wld(self):
        self.ax_wld.cla()

        self.ax_wld.set_xlabel("x_wld")
        self.ax_wld.set_ylabel("y_wld")
        self.ax_wld.set_zlabel("z_wld")
        self.ax_wld.set_xlim([-5, 5])
        self.ax_wld.set_ylim([-5, 5])
        self.ax_wld.set_zlim([-5, 5])
        self.ax_wld.set_title("obj wld")
        self.ax_wld.set_xticks(np.arange(-5, 5 + 1, 1))
        self.ax_wld.set_yticks(np.arange(-5, 5 + 1, 1))
        for i, l in enumerate(self.ll):
            x = np.array([self.Xpt[0][l[0]], self.Xpt[0][l[1]]])
            y = np.array([self.Xpt[1][l[0]], self.Xpt[1][l[1]]])
            z = np.array([self.Xpt[2][l[0]], self.Xpt[2][l[1]]])
            self.ax_wld.plot(x, y, z, marker='.', markersize=5, color=self.llcolor[i])

        # ワールド座標
        orgWld = np.array([0, 0, 0])
        axWld_ax1 = np.array([1, 0, 0])
        axWld_ax2 = np.array([0, 1, 0])
        axWld_ax3 = np.array([0, 0, 1])
        self.ax_wld.quiver(orgWld[0], orgWld[1], orgWld[2], axWld_ax1[0], axWld_ax1[1], axWld_ax1[2], length=1, color='g')
        self.ax_wld.quiver(orgWld[0], orgWld[1], orgWld[2], axWld_ax2[0], axWld_ax2[1], axWld_ax2[2], length=1, color='g')
        self.ax_wld.quiver(orgWld[0], orgWld[1], orgWld[2], axWld_ax3[0], axWld_ax3[1], axWld_ax3[2], length=1, color='g')

        # # 軸の移動（原点、終点を逆方向に移動）
        # # cam1
        # orgPos_st = np.array([orgWld[0],orgWld[1],orgWld[2],1])
        # orgPos_edx = np.array([axWld_ax1[0], axWld_ax1[1], axWld_ax1[2], 1])
        # orgPos_edy = np.array([axWld_ax2[0], axWld_ax2[1], axWld_ax2[2], 1])
        # orgPos_edz = np.array([axWld_ax3[0], axWld_ax3[1], axWld_ax3[2], 1])
        # Rmat, jac = cv2.Rodrigues(np.array([[-np.rad2deg(self.Ang_x_cam1),
        #                                      -np.rad2deg(self.Ang_y_cam1),
        #                                      -np.rad2deg(self.Ang_z_cam1)]], float))
        # Pmat = np.array([[Rmat[0][0], Rmat[0][1], Rmat[0][2], -self.Trans_x_cam1],
        #                       [Rmat[1][0], Rmat[1][1], Rmat[1][2], -self.Trans_y_cam1],
        #                       [Rmat[2][0], Rmat[2][1], Rmat[2][2], -self.Trans_z_cam1]])
        # orgCam = Pmat.dot(orgPos_st)
        # orgPos_edx_cam1 = Pmat.dot(orgPos_edx)
        # orgPos_edy_cam1 = Pmat.dot(orgPos_edy)
        # orgPos_edz_cam1 = Pmat.dot(orgPos_edz)
        # axCam_ax1 = orgPos_edx_cam1 - orgCam
        # axCam_ax2 = orgPos_edy_cam1 - orgCam
        # axCam_ax3 = orgPos_edz_cam1 - orgCam
        # self.ax_wld.quiver(orgCam[0], orgCam[1], orgCam[2], axCam_ax1[0], axCam_ax1[1], axCam_ax1[2], length=1, color='orange')
        #
        # # cam1
        # orgPos_st = np.array([orgWld[0],orgWld[1],orgWld[2],1])
        # orgPos_edx = np.array([axWld_ax1[0], axWld_ax1[1], axWld_ax1[2], 1])
        # orgPos_edy = np.array([axWld_ax2[0], axWld_ax2[1], axWld_ax2[2], 1])
        # orgPos_edz = np.array([axWld_ax3[0], axWld_ax3[1], axWld_ax3[2], 1])
        # Rmat, jac = cv2.Rodrigues(np.array([[-np.rad2deg(self.Ang_x_cam2),
        #                                      -np.rad2deg(self.Ang_y_cam2),
        #                                      -np.rad2deg(self.Ang_z_cam2)]], float))
        # Pmat = np.array([[Rmat[0][0], Rmat[0][1], Rmat[0][2], -self.Trans_x_cam2],
        #                       [Rmat[1][0], Rmat[1][1], Rmat[1][2], -self.Trans_y_cam2],
        #                       [Rmat[2][0], Rmat[2][1], Rmat[2][2], -self.Trans_z_cam2]])
        # orgCam = Pmat.dot(orgPos_st)
        # orgPos_edx_cam2 = Pmat.dot(orgPos_edx)
        # orgPos_edy_cam2 = Pmat.dot(orgPos_edy)
        # orgPos_edz_cam2 = Pmat.dot(orgPos_edz)
        # axCam_ax1 = orgPos_edx_cam2 - orgCam
        # axCam_ax2 = orgPos_edy_cam2 - orgCam
        # axCam_ax3 = orgPos_edz_cam2 - orgCam
        # self.ax_wld.quiver(orgCam[0], orgCam[1], orgCam[2], axCam_ax1[0], axCam_ax1[1], axCam_ax1[2], length=1,color='orange')
        # self.ax_wld.quiver(orgCam[0], orgCam[1], orgCam[2], axCam_ax2[0], axCam_ax2[1], axCam_ax2[2], length=1,color='orange')
        # self.ax_wld.quiver(orgCam[0], orgCam[1], orgCam[2], axCam_ax3[0], axCam_ax3[1], axCam_ax3[2], length=1,color='orange')
        #

    def draw3d_reconstracted(self):
        self.ax_rcn.cla()

        # カメラ行列（内部・外部）
        M1 = self.K.dot(self.P1)
        M2 = self.K.dot(self.P2)

        #　画像座標 ( sx, sy, s )
        x1p = M1.dot(self.Xpt)
        x2p = M2.dot(self.Xpt)
        
        # sで正規化 (x, y, 1)
        for i in range(3):
            x1p[i] /= x1p[2]
            x2p[i] /= x2p[2]

        # 三角測量と正規化 (X,Y,Z,1)
        X = sfm.triangulate(x1p, x2p, M1, M2)

        self.ax_rcn.set_xlabel("x_wld_rcn")
        self.ax_rcn.set_ylabel("y_wld_rcn")
        self.ax_rcn.set_zlabel("z_wld_rcn")
        self.ax_rcn.set_xlim([-5, 5])
        self.ax_rcn.set_ylim([-5, 5])
        self.ax_rcn.set_zlim([-5, 5])
        self.ax_rcn.set_title("obj wld rcn")
        for l in self.ll:
            x = np.array([X[0][l[0]], X[0][l[1]]])
            y = np.array([X[1][l[0]], X[1][l[1]]])
            z = np.array([X[2][l[0]], X[2][l[1]]])
            self.ax_rcn.plot(x, y, z, marker='.', markersize=5, color='red')

    def draw3d_reconstracted_estP(self):
        self.ax_rcn_est.cla()

        # カメラ行列（内部・外部）
        M1 = self.K.dot(self.P1)
        M2 = self.K.dot(self.P2)

        # 　画像座標 ( sx, sy, s )
        x1p = M1.dot(self.Xpt)
        x2p = M2.dot(self.Xpt)

        # sで正規化 (x, y, 1)
        for i in range(3):
            x1p[i] /= x1p[2]
            x2p[i] /= x2p[2]

        # pts1 = []
        # pts2 = []
        # for i in range(len(x1p[0])):
        #     pts1.append([x1p[0][i], x1p[1][i]])
        #     pts2.append([x2p[0][i], x2p[1][i]])
        # pts1 = np.int32(pts1)
        # pts2 = np.int32(pts2)

        # 画像1, 画像2の特徴点を対応付ける行列Fを計算
        # F, mask = cv2.findFundamentalMat(pts1, pts2, cv2.FM_RANSAC)
        # mask = np.reshape(mask, (1, len(mask)))[0]
        # idx_mask = np.arange(len(mask))
        # idx_mask = idx_mask[mask == 1]

        x1n = np.dot(inv(self.K), x1p)
        x2n = np.dot(inv(self.K), x2p)

        # RANSACでEを推定
        # Method_EstE = "RAN"
        Method_EstE = ""
        E = ""
        inliers = ""
        if Method_EstE is "RAN":
            model = sfm.RansacModel()
            E, inliers = sfm.F_from_ransac(x1n, x2n, model)
        else:
            E = sfm.compute_fundamental(x1n, x2n)
            inliers = [ True for i in range(len(x1n[0,:]))]

        print("E: ", E)

        # # カメラ行列を計算する（P2は4つの解のリスト）
        P1 = array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]])
        P2, S, R1, R2, U, V = sfm.compute_P_from_essential_mod(E)

        print("S: ", S)
        print("S fro: ", np.linalg.norm(S, "fro"))

        print("R1: ", R1)
        print("R2: ", R2)
        print("R1 deg: ", calcRmatDeg(R1))
        print("R2 deg: ", calcRmatDeg(R2))
        P2_R = self.P2[:,0:3]
        print("P2_R: ", P2_R)
        # print("U: ", U)
        # print("V: ", V)
        # print("S*R1: ", S.dot(R1))
        # print("S*R2: ", S.dot(R2))


        # 2つのカメラの前に点のある解を選ぶ
        ind = 0
        maxres = 0
        for i in range(4):
            # triangulate inliers and compute depth for each camera
            # インライアを三角測量し各カメラからの奥行きを計算する
            X = sfm.triangulate(x1n[:, inliers], x2n[:, inliers], P1, P2[i])
            d1 = np.dot(P1, X)[2]
            d2 = np.dot(P2[i], X)[2]
            if sum(d1 > 0) + sum(d2 > 0) > maxres:
                maxres = sum(d1 > 0) + sum(d2 > 0)
                ind = i
                infront = (d1 > 0) & (d2 > 0)

        #全表示用
        M1 = self.K.dot(P1)
        M2_est = self.K.dot(P2[ind])
        X = sfm.triangulate(x1p, x2p, M1, M2_est)

        # print("P2 est:", P2[ind])
        # print("P2: ", self.P2)

        # for i in range(4):
        #     print("P2 est[ ", i, " ]: ", P2[i])
        #
        # M2 = self.K.dot(self.P2)
        # print("M2: ", M2)

        self.ax_rcn_est.set_xlabel("x_wld_rcn")
        self.ax_rcn_est.set_ylabel("y_wld_rcn")
        self.ax_rcn_est.set_zlabel("z_wld_rcn")
        # self.ax_rcn_est.set_xlim([-5, 5])
        # self.ax_rcn_est.set_ylim([-5, 5])
        # self.ax_rcn_est.set_zlim([-5, 5])
        self.ax_rcn_est.set_title("obj wld rcn est")
        for l in self.ll:
            x = np.array([X[0][l[0]], X[0][l[1]]])
            y = np.array([X[1][l[0]], X[1][l[1]]])
            z = np.array([X[2][l[0]], X[2][l[1]]])
            self.ax_rcn_est.plot(x, y, z, marker='.', markersize=5, color='red')

        # # 対応が見つからなかった点
        # x = X[0,[ not val for val in mask]]
        # y = X[1,[ not val for val in mask]]
        # z = X[2,[ not val for val in mask]]
        # self.ax_rcn_est.plot(x, y, z, marker='.', markersize=5, color='black', linestyle = "")

        # カメラより奥にあると推定された点
        # X = sfm.triangulate(x1[:, idx_mask], x2[:, idx_mask], P1, P2[i])
        x = X[0,[ not val for val in infront]]
        y = X[1,[ not val for val in infront]]
        z = X[2,[ not val for val in infront]]
        self.ax_rcn_est.plot(x, y, z, marker='.', markersize=5, color='blue', linestyle = "")

        # #
        # for i, inf in enumerate(infront):
        #     if inf :
        #         x = np.array([X[0][i], X[0][i]])
        #         y = np.array([X[1][i], X[1][i]])
        #         z = np.array([X[2][i], X[2][i]])
        #         self.ax_rcn_est.scatter(x, y, z, markersize=5, color='black')

if __name__ == '__main__':
    ex = TKExample()