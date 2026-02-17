try:
    from langchain.tools import BaseTool
    print('BaseTool found in langchain.tools')
except ImportError:
    try:
        from langchain_core.tools import BaseTool
        print('BaseTool found in langchain_core.tools')
    except ImportError:
        print('BaseTool not found')

try:
    from langchain.callbacks.manager import CallbackManagerForToolRun
    print('CallbackManagerForToolRun found in langchain.callbacks.manager')
except ImportError:
    try:
        from langchain_core.callbacks.manager import CallbackManagerForToolRun
        print('CallbackManagerForToolRun found in langchain_core.callbacks.manager')
    except ImportError:
        print('CallbackManagerForToolRun not found')
