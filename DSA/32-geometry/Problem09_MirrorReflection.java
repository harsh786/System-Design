public class Problem09_MirrorReflection {
    public static int mirrorReflection(int p, int q) {
        while (p % 2 == 0 && q % 2 == 0) { p /= 2; q /= 2; }
        if (p % 2 == 0) return 2;
        if (q % 2 == 0) return 0;
        return 1;
    }
    public static void main(String[] args) {
        System.out.println(mirrorReflection(2, 1)); // 2
    }
}
