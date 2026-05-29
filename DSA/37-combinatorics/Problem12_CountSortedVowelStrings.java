public class Problem12_CountSortedVowelStrings {
    public int countVowelStrings(int n) {
        // C(n+4, 4)
        return (n+1)*(n+2)*(n+3)*(n+4)/24;
    }

    public static void main(String[] args) {
        System.out.println(new Problem12_CountSortedVowelStrings().countVowelStrings(2)); // 15
    }
}
