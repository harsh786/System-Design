import java.util.*;
public class Problem11_SortAges {
    public void sortAges(int[] ages) { int[] count=new int[151]; for(int a:ages) count[a]++; int idx=0; for(int i=0;i<151;i++) while(count[i]-->0) ages[idx++]=i; }
    public static void main(String[] args){ Problem11_SortAges s=new Problem11_SortAges(); int[] a={25,30,25,18,45,30}; s.sortAges(a); System.out.println(Arrays.toString(a)); }
}
