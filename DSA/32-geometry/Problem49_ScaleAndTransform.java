public class Problem49_ScaleAndTransform {
    // 2D affine transformation matrix operations
    static class Transform {
        double[][] m = {{1,0,0},{0,1,0},{0,0,1}}; // identity
        Transform translate(double tx, double ty) {
            double[][] t = {{1,0,tx},{0,1,ty},{0,0,1}};
            m = multiply(t, m); return this;
        }
        Transform scale(double sx, double sy) {
            double[][] s = {{sx,0,0},{0,sy,0},{0,0,1}};
            m = multiply(s, m); return this;
        }
        Transform rotate(double theta) {
            double c = Math.cos(theta), s = Math.sin(theta);
            double[][] r = {{c,-s,0},{s,c,0},{0,0,1}};
            m = multiply(r, m); return this;
        }
        double[] apply(double x, double y) {
            return new double[]{m[0][0]*x + m[0][1]*y + m[0][2], m[1][0]*x + m[1][1]*y + m[1][2]};
        }
        static double[][] multiply(double[][] a, double[][] b) {
            double[][] res = new double[3][3];
            for (int i = 0; i < 3; i++) for (int j = 0; j < 3; j++) for (int k = 0; k < 3; k++) res[i][j] += a[i][k]*b[k][j];
            return res;
        }
    }
    public static void main(String[] args) {
        Transform t = new Transform();
        t.translate(1, 1).scale(2, 2).rotate(Math.PI / 4);
        double[] p = t.apply(1, 0);
        System.out.printf("(%.4f, %.4f)%n", p[0], p[1]);
        // Simple scale test
        Transform t2 = new Transform();
        t2.scale(3, 3);
        double[] p2 = t2.apply(2, 4);
        System.out.printf("(%.1f, %.1f)%n", p2[0], p2[1]); // (6.0, 12.0)
    }
}
