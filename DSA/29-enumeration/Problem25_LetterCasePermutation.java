import java.util.*;

public class Problem25_LetterCasePermutation {
    public List<String> letterCasePermutation(String s) {
        List<String> result = new ArrayList<>();
        backtrack(result, s.toCharArray(), 0);
        return result;
    }
    private void backtrack(List<String> result, char[] arr, int idx) {
        if (idx == arr.length) { result.add(new String(arr)); return; }
        if (Character.isDigit(arr[idx])) { backtrack(result,arr,idx+1); return; }
        arr[idx] = Character.toLowerCase(arr[idx]); backtrack(result,arr,idx+1);
        arr[idx] = Character.toUpperCase(arr[idx]); backtrack(result,arr,idx+1);
    }
    public static void main(String[] args) { System.out.println(new Problem25_LetterCasePermutation().letterCasePermutation("a1b2")); }
}
