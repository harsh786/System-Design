public class Problem16_KthSymbolInGrammar {
    public int kthGrammar(int n, int k) {
        if (n == 1) return 0;
        int parent = kthGrammar(n - 1, (k + 1) / 2);
        if (k % 2 == 1) return parent;
        return parent == 0 ? 1 : 0;
    }

    public static void main(String[] args) {
        System.out.println(new Problem16_KthSymbolInGrammar().kthGrammar(4, 5)); // 1
    }
}
