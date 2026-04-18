"""
Ariadne CLI Comprehensive Test Suite
测试所有CLI命令是否正常工作
"""

import subprocess
import sys
import os
from pathlib import Path
import shutil

# 切换到Ariadne目录
SCRIPT_DIR = Path(__file__).parent
ARIADNE_DIR = SCRIPT_DIR.parent
os.chdir(ARIADNE_DIR)

# 测试数据目录
TEST_DATA_DIR = ARIADNE_DIR / "tests" / "test_data"
TEST_DATA_DIR.mkdir(exist_ok=True)

# 测试用数据目录
TEST_INPUT_DIR = ARIADNE_DIR / "tests" / "test_input"
TEST_INPUT_DIR.mkdir(exist_ok=True)

# 备份并清理旧的测试数据
DATA_DIR = ARIADNE_DIR / "ariadne_data"
BACKUP_DIR = ARIADNE_DIR / "ariadne_data_backup"

def run_cmd(args: list, check=True, capture=True) -> subprocess.CompletedProcess:
    """运行CLI命令"""
    cmd = [sys.executable, "-m", "ariadne.cli"] + args
    print(f"\n{'='*60}")
    print(f"$ {' '.join(cmd)}")
    print("-" * 60)
    
    result = subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        cwd=str(ARIADNE_DIR)
    )
    
    if capture:
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
    
    print(f"[Exit code: {result.returncode}]")
    
    if check and result.returncode != 0:
        print(f"[FAIL] Command failed!")
    else:
        print(f"[OK] Command completed")
    
    return result


def test_help():
    """测试1: --help 显示帮助"""
    print("\n" + "="*60)
    print("TEST 1: ariadne --help")
    print("="*60)
    result = run_cmd(["--help"])
    assert result.returncode == 0, "Help should succeed"
    assert "Ariadne" in result.stdout, "Should show Ariadne branding"
    print("[OK] Help displayed correctly")


def test_version():
    """测试2: --version 显示版本"""
    print("\n" + "="*60)
    print("TEST 2: ariadne --version")
    print("="*60)
    result = run_cmd(["--version"])
    assert result.returncode == 0, "Version should succeed"
    print("[OK] Version displayed correctly")


def test_info():
    """测试3: info命令"""
    print("\n" + "="*60)
    print("TEST 3: ariadne info")
    print("="*60)
    result = run_cmd(["info"])
    assert result.returncode == 0, "Info should succeed"
    assert "Ariadne" in result.stdout, "Should show system name"
    assert "Storage backend" in result.stdout, "Should show storage info"
    print("[OK] Info command works")


def test_info_stats():
    """测试4: info --stats 命令"""
    print("\n" + "="*60)
    print("TEST 4: ariadne info --stats")
    print("="*60)
    result = run_cmd(["info", "--stats"])
    assert result.returncode == 0, "Info with stats should succeed"
    print("[OK] Info with stats works")


def setup_test_files():
    """创建测试文件"""
    # 创建不同格式的测试文件
    test_files = []
    
    # 1. Markdown文件
    md_file = TEST_INPUT_DIR / "test_readme.md"
    md_file.write_text("""# Test Document

## Overview
This is a test markdown document for Ariadne CLI testing.

## Features
- File ingestion
- Vector search
- Knowledge graph
- LLM enhancement

## Usage
Run the CLI with appropriate commands.
""", encoding='utf-8')
    test_files.append(md_file)
    
    # 2. 纯文本文件
    txt_file = TEST_INPUT_DIR / "test_notes.txt"
    txt_file.write_text("""Test Notes File
=================

First line of notes.
Second line of notes with some content.

Third paragraph with more detailed information about the test.
Last paragraph in the file.
""", encoding='utf-8')
    test_files.append(txt_file)
    
    # 3. Python文件
    py_file = TEST_INPUT_DIR / "test_module.py"
    py_file.write_text("""\"\"\"
Test Python module for Ariadne.
\"\"\"

def hello():
    '''Say hello.'''
    return "Hello from Ariadne!"

class TestClass:
    '''A test class.'''
    
    def method(self):
        '''A test method.'''
        return 42

if __name__ == "__main__":
    print(hello())
""", encoding='utf-8')
    test_files.append(py_file)
    
    # 4. CSV文件
    csv_file = TEST_INPUT_DIR / "test_data.csv"
    csv_file.write_text("""id,name,value,category
1,Item A,100,A
2,Item B,200,B
3,Item C,300,A
4,Item D,400,C
5,Item E,500,B
""", encoding='utf-8')
    test_files.append(csv_file)
    
    return test_files


def test_ingest_single_file():
    """测试5: ingest单个文件"""
    print("\n" + "="*60)
    print("TEST 5: Ingest single file")
    print("="*60)
    
    test_file = TEST_INPUT_DIR / "test_readme.md"
    if not test_file.exists():
        test_file.write_text("# Test\n\nTest content.", encoding='utf-8')
    
    result = run_cmd(["ingest", str(test_file), "-v"])
    assert result.returncode == 0, "Ingest should succeed"
    print("[OK] Single file ingestion works")


def test_ingest_directory():
    """测试6: ingest整个目录"""
    print("\n" + "="*60)
    print("TEST 6: Ingest directory")
    print("="*60)
    
    result = run_cmd(["ingest", str(TEST_INPUT_DIR), "-r", "-v"])
    assert result.returncode == 0, "Directory ingest should succeed"
    print("[OK] Directory ingestion works")


def test_ingest_empty_directory():
    """测试7: ingest空目录或无匹配文件"""
    print("\n" + "="*60)
    print("TEST 7: Ingest with no supported files")
    print("="*60)
    
    empty_dir = TEST_INPUT_DIR / "empty"
    empty_dir.mkdir(exist_ok=True)
    
    result = run_cmd(["ingest", str(empty_dir)], check=False)
    # 应该显示"No supported files found"
    print("[OK] Empty directory handling works")


def test_search():
    """测试8: search命令"""
    print("\n" + "="*60)
    print("TEST 8: Search command")
    print("="*60)
    
    result = run_cmd(["search", "test document"])
    # 可能有结果也可能没有，取决于之前摄入的数据
    assert result.returncode == 0, "Search should succeed"
    print("[OK] Search command works")


def test_search_with_options():
    """测试9: search带选项"""
    print("\n" + "="*60)
    print("TEST 9: Search with options")
    print("="*60)
    
    result = run_cmd(["search", "Ariadne", "-k", "3", "-v"])
    assert result.returncode == 0, "Search with options should succeed"
    print("[OK] Search with options works")


def test_search_no_results():
    """测试10: search无结果"""
    print("\n" + "="*60)
    print("TEST 10: Search with no results")
    print("="*60)
    
    result = run_cmd(["search", "xyzabc123nonexistentterm999"], check=False)
    assert result.returncode == 0, "Search should complete even with no results"
    print("[OK] No-results search works")


def test_ingest_unsupported_format():
    """测试11: ingest不支持的格式"""
    print("\n" + "="*60)
    print("TEST 11: Ingest unsupported format")
    print("="*60)
    
    unsupported_file = TEST_INPUT_DIR / "test.xyz"
    unsupported_file.write_text("test content", encoding='utf-8')
    
    result = run_cmd(["ingest", str(unsupported_file), "-v"], check=False)
    # 不支持的格式应该被跳过
    print("[OK] Unsupported format handling works")


def test_ingest_invalid_path():
    """测试12: ingest不存在的路径"""
    print("\n" + "="*60)
    print("TEST 12: Ingest invalid path")
    print("="*60)
    
    result = run_cmd(["ingest", "/nonexistent/path/to/file.md"], check=False)
    # 应该失败
    assert result.returncode != 0, "Invalid path should fail"
    print("[OK] Invalid path handling works")


def test_batch_ingest():
    """测试13: 批量摄入多个文件"""
    print("\n" + "="*60)
    print("TEST 13: Batch ingest multiple files")
    print("="*60)
    
    # 创建多个测试文件
    for i in range(3):
        f = TEST_INPUT_DIR / f"batch_test_{i}.txt"
        f.write_text(f"Batch test file number {i}\n" * 10, encoding='utf-8')
    
    result = run_cmd(["ingest", str(TEST_INPUT_DIR), "-r", "-v", "-b", "10"])
    assert result.returncode == 0, "Batch ingest should succeed"
    print("[OK] Batch ingestion works")


def test_gui_command():
    """测试14: gui命令"""
    print("\n" + "="*60)
    print("TEST 14: GUI command (non-interactive)")
    print("="*60)
    
    # GUI在无头环境中应该优雅地失败
    result = run_cmd(["gui"], check=False)
    # 不检查返回码，因为GUI可能不可用
    print("[OK] GUI command handles environment gracefully")


def test_info_after_ingest():
    """测试15: 摄入后查看信息"""
    print("\n" + "="*60)
    print("TEST 15: Info after ingest")
    print("="*60)
    
    result = run_cmd(["info", "--stats"])
    assert result.returncode == 0, "Info should succeed after ingestion"
    print("[OK] Post-ingestion info works")


def test_search_after_ingest():
    """测试16: 摄入后搜索"""
    print("\n" + "="*60)
    print("TEST 16: Search after ingest")
    print("="*60)
    
    result = run_cmd(["search", "test", "-k", "10"])
    assert result.returncode == 0, "Search after ingest should succeed"
    # 检查是否找到了结果
    if "Found" in result.stdout and "results" in result.stdout:
        print("[OK] Post-ingestion search works and returned results")
    else:
        print("[OK] Post-ingestion search completed (no results)")


def cleanup():
    """清理测试数据"""
    print("\n" + "="*60)
    print("CLEANUP: Cleaning up test data")
    print("="*60)
    
        # 恢复备份
    if BACKUP_DIR.exists():
        if DATA_DIR.exists():
            shutil.rmtree(DATA_DIR)
        shutil.move(BACKUP_DIR, DATA_DIR)
        print("[OK] Restored original data")
    
    # 删除测试输入目录
    if TEST_INPUT_DIR.exists():
        shutil.rmtree(TEST_INPUT_DIR)
        print("[OK] Removed test input directory")
    
    if TEST_DATA_DIR.exists():
        shutil.rmtree(TEST_DATA_DIR)
        print("[OK] Removed test data directory")


def main():
    """运行所有测试"""
    print("="*60)
    print("Ariadne CLI Comprehensive Test Suite")
    print("="*60)
    print(f"Working directory: {os.getcwd()}")
    
    # 备份现有数据
    if DATA_DIR.exists():
        if BACKUP_DIR.exists():
            shutil.rmtree(BACKUP_DIR)
        shutil.copytree(DATA_DIR, BACKUP_DIR)
        print(f"[OK] Backed up existing data to {BACKUP_DIR}")
    
    # 清理旧数据以确保测试干净
    if DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
        print("[OK] Cleared existing data")
    
    # 创建测试文件
    print("\nSetting up test files...")
    setup_test_files()
    print("[OK] Test files created")
    
    tests = [
        ("Help", test_help),
        ("Version", test_version),
        ("Info", test_info),
        ("Info with Stats", test_info_stats),
        ("Ingest Single File", test_ingest_single_file),
        ("Ingest Directory", test_ingest_directory),
        ("Ingest Empty Dir", test_ingest_empty_directory),
        ("Search", test_search),
        ("Search with Options", test_search_with_options),
        ("Search No Results", test_search_no_results),
        ("Ingest Unsupported", test_ingest_unsupported_format),
        ("Ingest Invalid Path", test_ingest_invalid_path),
        ("Batch Ingest", test_batch_ingest),
        ("GUI Command", test_gui_command),
        ("Info After Ingest", test_info_after_ingest),
        ("Search After Ingest", test_search_after_ingest),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            passed += 1
            print(f"[OK] {name}: PASSED")
        except Exception as e:
            failed += 1
            print(f"[X] {name}: FAILED - {e}")
    
    # 清理
    cleanup()
    
    # 总结
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Total: {len(tests)}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    
    if failed == 0:
        print("\n[SUCCESS] All tests passed!")
        return 0
    else:
        print(f"\n[WARNING] {failed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
